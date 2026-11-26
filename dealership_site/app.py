import os
import sqlite3
from datetime import date

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dealership.db")

app = Flask(__name__)
app.secret_key = "change-me-for-class-project"

STATUSES = ["Available", "Pending", "Sold"]


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def one(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def run(sql, args=()):
    """Run a write. Returns True on success, flashes the error otherwise."""
    db = get_db()
    try:
        db.execute(sql, args)
        db.commit()
        return True
    except sqlite3.Error as e:
        db.rollback()
        flash(f"Could not save: {e}", "error")
        return False


def next_customer_id():
    row = one("SELECT MAX(CAST(SUBSTR(CustomerID, 2) AS INTEGER)) AS m FROM Customer")
    return "C%08d" % ((row["m"] or 0) + 1)


def refresh_sales_metrics():
    """SalesMetrics = number of vehicles a salesperson has sold."""
    get_db().execute(
        """UPDATE Salesperson SET SalesMetrics =
           (SELECT COUNT(*) FROM "Transaction" t WHERE t.SalespersonID = Salesperson.EmployeeID)"""
    )
    get_db().commit()


# ---------- home ----------
@app.route("/")
def home():
    stats = {
        "vehicles": one("SELECT COUNT(*) c FROM Vehicle")["c"],
        "available": one("SELECT COUNT(*) c FROM Vehicle WHERE Status='Available'")["c"],
        "customers": one("SELECT COUNT(*) c FROM Customer")["c"],
        "sales": one('SELECT COUNT(*) c FROM "Transaction"')["c"],
    }
    return render_template("home.html", stats=stats)


# ---------- vehicles ----------
@app.route("/vehicles")
def vehicles():
    rows = query(
        """SELECT v.*,
                  CASE WHEN n.VIN IS NOT NULL THEN 'New'
                       WHEN u.VIN IS NOT NULL THEN 'Used' ELSE 'Unclassified' END AS Type,
                  n.MSRP, n.ManufacturerSpecial, u.Mileage, u.FactoryWarranty, u.TotalMoneySpent
           FROM Vehicle v
           LEFT JOIN New_Vehicle n ON n.VIN = v.VIN
           LEFT JOIN Used_Vehicle u ON u.VIN = v.VIN
           ORDER BY v.Make, v.Model"""
    )
    return render_template("vehicles.html", rows=rows)


def save_vehicle(form, existing_vin=None):
    vin = (existing_vin or form["vin"]).strip().upper()
    vtype = form["vtype"]
    db = get_db()
    try:
        if existing_vin:
            db.execute(
                "UPDATE Vehicle SET Make=?, Model=?, VehicleYear=?, Status=?, Color=? WHERE VIN=?",
                (form["make"], form["model"], form["year"], form["status"], form["color"], vin),
            )
        else:
            db.execute(
                "INSERT INTO Vehicle VALUES (?,?,?,?,?,?)",
                (vin, form["make"], form["model"], form["year"], form["status"], form["color"]),
            )
            if vtype == "Used":
                db.execute(
                    "INSERT INTO Used_Vehicle VALUES (?,?,?,?)",
                    (vin, form["mileage"], form.get("warranty") or None, form["spent"]),
                )
            else:
                db.execute(
                    "INSERT INTO New_Vehicle VALUES (?,?,?)",
                    (vin, form["msrp"], form["special"]),
                )
        if existing_vin:
            if vtype == "Used":
                db.execute(
                    "UPDATE Used_Vehicle SET Mileage=?, FactoryWarranty=?, TotalMoneySpent=? WHERE VIN=?",
                    (form["mileage"], form.get("warranty") or None, form["spent"], vin),
                )
            else:
                db.execute(
                    "UPDATE New_Vehicle SET MSRP=?, ManufacturerSpecial=? WHERE VIN=?",
                    (form["msrp"], form["special"], vin),
                )
        db.commit()
        return True
    except (sqlite3.Error, KeyError) as e:
        db.rollback()
        flash(f"Could not save vehicle: {e}", "error")
        return False


@app.route("/vehicles/new", methods=["GET", "POST"])
def vehicle_new():
    if request.method == "POST":
        if save_vehicle(request.form):
            flash("Vehicle added.", "success")
            return redirect(url_for("vehicles"))
    return render_template("vehicle_form.html", v=request.form or {}, statuses=STATUSES, editing=False)


@app.route("/vehicles/<vin>/edit", methods=["GET", "POST"])
def vehicle_edit(vin):
    row = one(
        """SELECT v.*, n.MSRP, n.ManufacturerSpecial, u.Mileage, u.FactoryWarranty, u.TotalMoneySpent,
                  CASE WHEN n.VIN IS NOT NULL THEN 'New' ELSE 'Used' END AS Type
           FROM Vehicle v LEFT JOIN New_Vehicle n ON n.VIN=v.VIN LEFT JOIN Used_Vehicle u ON u.VIN=v.VIN
           WHERE v.VIN=?""",
        (vin,),
    )
    if row is None:
        flash("Vehicle not found.", "error")
        return redirect(url_for("vehicles"))
    if request.method == "POST":
        form = request.form.copy()
        form["vtype"] = row["Type"]  # type cannot change (disjoint subtypes)
        if save_vehicle(form, existing_vin=vin):
            flash("Vehicle updated.", "success")
            return redirect(url_for("vehicles"))
    return render_template("vehicle_form.html", v=dict(row), statuses=STATUSES, editing=True)


@app.route("/vehicles/<vin>/delete", methods=["POST"])
def vehicle_delete(vin):
    db = get_db()
    try:
        db.execute("DELETE FROM Used_Vehicle WHERE VIN=?", (vin,))
        db.execute("DELETE FROM New_Vehicle WHERE VIN=?", (vin,))
        db.execute("DELETE FROM Vehicle WHERE VIN=?", (vin,))
        db.commit()
        flash("Vehicle deleted.", "success")
    except sqlite3.Error:
        db.rollback()
        flash("This vehicle is part of a sale and cannot be deleted.", "error")
    return redirect(url_for("vehicles"))


# ---------- customers ----------
@app.route("/customers")
def customers():
    rows = query(
        """SELECT c.*, COUNT(t.TransactionID) AS Purchases
           FROM Customer c LEFT JOIN "Transaction" t ON t.CustomerID=c.CustomerID
           GROUP BY c.CustomerID ORDER BY c.Name"""
    )
    return render_template("customers.html", rows=rows)


@app.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    if request.method == "POST":
        if run("INSERT INTO Customer VALUES (?,?)", (next_customer_id(), request.form["name"].strip())):
            flash("Customer added.", "success")
            return redirect(url_for("customers"))
    return render_template("customer_form.html", c=request.form or {}, editing=False)


@app.route("/customers/<cid>/edit", methods=["GET", "POST"])
def customer_edit(cid):
    row = one("SELECT * FROM Customer WHERE CustomerID=?", (cid,))
    if row is None:
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))
    if request.method == "POST":
        if run("UPDATE Customer SET Name=? WHERE CustomerID=?", (request.form["name"].strip(), cid)):
            flash("Customer updated.", "success")
            return redirect(url_for("customers"))
    return render_template("customer_form.html", c=dict(row), editing=True)


@app.route("/customers/<cid>/delete", methods=["POST"])
def customer_delete(cid):
    if run("DELETE FROM Customer WHERE CustomerID=?", (cid,)):
        flash("Customer deleted.", "success")
    return redirect(url_for("customers"))


# ---------- employees ----------
@app.route("/employees")
def employees():
    rows = query(
        """SELECT e.EmployeeID, e.Name, e.HiringDate,
                  CASE WHEN m.EmployeeID IS NOT NULL THEN 'Manager'
                       WHEN s.EmployeeID IS NOT NULL THEN 'Salesperson' ELSE 'Neither' END AS Role,
                  s.SalesMetrics, boss.Name AS ManagerName
           FROM Employee e
           LEFT JOIN Manager m ON m.EmployeeID=e.EmployeeID
           LEFT JOIN Salesperson s ON s.EmployeeID=e.EmployeeID
           LEFT JOIN Employee boss ON boss.EmployeeID=s.ManagerID
           ORDER BY e.Name"""
    )
    return render_template("employees.html", rows=rows)


@app.route("/employees/new", methods=["GET", "POST"])
def employee_new():
    managers = query("SELECT e.EmployeeID, e.Name FROM Manager m JOIN Employee e USING(EmployeeID)")
    if request.method == "POST":
        f = request.form
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO Employee (Name, SSN, HiringDate) VALUES (?,?,?)",
                (f["name"].strip(), f["ssn"].strip(), f["hired"]),
            )
            eid = cur.lastrowid
            if f["role"] == "Manager":
                db.execute("INSERT INTO Manager VALUES (?)", (eid,))
            elif f["role"] == "Salesperson":
                db.execute("INSERT INTO Salesperson VALUES (?,?,0)", (eid, f["manager"]))
            db.commit()
            flash("Employee added.", "success")
            return redirect(url_for("employees"))
        except (sqlite3.Error, KeyError) as e:
            db.rollback()
            flash(f"Could not save employee: {e}", "error")
    return render_template("employee_form.html", e=request.form or {}, managers=managers, today=date.today().isoformat())


@app.route("/employees/<int:eid>/delete", methods=["POST"])
def employee_delete(eid):
    db = get_db()
    try:
        db.execute("DELETE FROM Salesperson WHERE EmployeeID=?", (eid,))
        db.execute("DELETE FROM Manager WHERE EmployeeID=?", (eid,))
        db.execute("DELETE FROM Employee WHERE EmployeeID=?", (eid,))
        db.commit()
        flash("Employee deleted.", "success")
    except sqlite3.Error:
        db.rollback()
        flash("This employee still has sales or supervises salespeople, so cannot be deleted.", "error")
    return redirect(url_for("employees"))


# ---------- transactions ----------
@app.route("/transactions")
def transactions():
    rows = query(
        """SELECT t.TransactionID, t.Amount, t.SalesDate, t.VIN,
                  v.Make || ' ' || v.Model || ' ' || v.VehicleYear AS Vehicle,
                  c.Name AS Customer, e.Name AS Salesperson
           FROM "Transaction" t
           JOIN Vehicle v ON v.VIN=t.VIN
           JOIN Customer c ON c.CustomerID=t.CustomerID
           JOIN Employee e ON e.EmployeeID=t.SalespersonID
           ORDER BY t.SalesDate DESC, t.TransactionID DESC"""
    )
    return render_template("transactions.html", rows=rows)


@app.route("/transactions/new", methods=["GET", "POST"])
def transaction_new():
    avail = query("SELECT VIN, Make, Model, VehicleYear FROM Vehicle WHERE Status!='Sold' ORDER BY Make, Model")
    custs = query("SELECT CustomerID, Name FROM Customer ORDER BY Name")
    sellers = query("SELECT e.EmployeeID, e.Name FROM Salesperson s JOIN Employee e USING(EmployeeID) ORDER BY e.Name")
    if request.method == "POST":
        f = request.form
        db = get_db()
        try:
            db.execute(
                'INSERT INTO "Transaction" (Amount, VIN, CustomerID, SalespersonID, SalesDate) VALUES (?,?,?,?,?)',
                (f["amount"], f["vin"], f["customer"], f["seller"], f["date"]),
            )
            db.execute("UPDATE Vehicle SET Status='Sold' WHERE VIN=?", (f["vin"],))
            db.commit()
            refresh_sales_metrics()
            flash("Sale recorded.", "success")
            return redirect(url_for("transactions"))
        except (sqlite3.Error, KeyError) as e:
            db.rollback()
            flash(f"Could not record sale: {e}", "error")
    return render_template(
        "transaction_form.html", t=request.form or {}, avail=avail, custs=custs,
        sellers=sellers, today=date.today().isoformat()
    )


@app.route("/transactions/<int:tid>/delete", methods=["POST"])
def transaction_delete(tid):
    row = one('SELECT VIN FROM "Transaction" WHERE TransactionID=?', (tid,))
    if row:
        db = get_db()
        db.execute('DELETE FROM "Transaction" WHERE TransactionID=?', (tid,))
        db.execute("UPDATE Vehicle SET Status='Available' WHERE VIN=?", (row["VIN"],))
        db.commit()
        refresh_sales_metrics()
        flash("Sale removed and vehicle marked Available.", "success")
    return redirect(url_for("transactions"))


# ---------- reports ----------
@app.route("/reports")
def reports():
    perf = query(
        """SELECT e.Name, boss.Name AS ManagerName, s.SalesMetrics AS VehiclesSold,
                  COALESCE(SUM(t.Amount), 0) AS Revenue
           FROM Salesperson s
           JOIN Employee e ON e.EmployeeID=s.EmployeeID
           JOIN Employee boss ON boss.EmployeeID=s.ManagerID
           LEFT JOIN "Transaction" t ON t.SalespersonID=s.EmployeeID
           GROUP BY s.EmployeeID ORDER BY Revenue DESC"""
    )
    inventory = query(
        """SELECT v.VIN, v.Make, v.Model, v.VehicleYear, v.Color, v.Status,
                  CASE WHEN n.VIN IS NOT NULL THEN 'New' ELSE 'Used' END AS Type
           FROM Vehicle v LEFT JOIN New_Vehicle n ON n.VIN=v.VIN
           WHERE v.Status='Available' ORDER BY v.Make, v.Model"""
    )
    history = query(
        """SELECT c.Name, v.Make || ' ' || v.Model || ' ' || v.VehicleYear AS Vehicle,
                  t.SalesDate, t.Amount
           FROM "Transaction" t JOIN Customer c ON c.CustomerID=t.CustomerID
           JOIN Vehicle v ON v.VIN=t.VIN ORDER BY c.Name, t.SalesDate"""
    )
    return render_template("reports.html", perf=perf, inventory=inventory, history=history)


if __name__ == "__main__":
    app.run(debug=True)
