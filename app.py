import os
import io
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from functools import wraps
from datetime import datetime
from openpyxl import Workbook
from reportlab.pdfgen import canvas

# --- Flask App Config ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///invoices.db")
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Logging ---
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')

# --- Company Info ---
COMPANY = {
    "name": "HITS Hub Innovative Software Company",
    "address": "Kano, Nigeria",
    "phone": "+2348065395103"
}
app.jinja_env.globals.update(COMPANY=COMPANY)
app.jinja_env.globals.update(datetime=datetime)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(150), nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)
    discount_rate = db.Column(db.Float, default=0.0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('InvoiceItem', backref='invoice', cascade="all, delete-orphan")

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    name = db.Column(db.String(150), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

# --- Login Required Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Utility: Calculate Totals ---
def calculate_invoice_totals(invoice):
    subtotal = sum(item.qty * item.price for item in invoice.items)
    tax_amount = subtotal * (invoice.tax_rate / 100)
    discount_amount = subtotal * (invoice.discount_rate / 100)
    total = subtotal + tax_amount - discount_amount
    return subtotal, tax_amount, discount_amount, total

app.jinja_env.globals.update(calculate_invoice_totals=calculate_invoice_totals)

# --- Routes ---
@app.route('/')
@login_required
def index():
    invoices = Invoice.query.order_by(Invoice.date_created.desc()).all()
    return render_template('index.html', invoices=invoices)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/invoice/new', methods=['GET', 'POST'])
@login_required
def new_invoice():
    if request.method == 'POST':
        client_name = request.form.get('client_name', '').strip()
        tax_rate = float(request.form.get('tax_rate', 0))
        discount_rate = float(request.form.get('discount_rate', 0))
        invoice = Invoice(client_name=client_name, tax_rate=tax_rate, discount_rate=discount_rate)
        db.session.add(invoice)
        db.session.commit()

        names = request.form.getlist('item_name[]')
        qtys = request.form.getlist('item_qty[]')
        prices = request.form.getlist('item_price[]')
        for name, qty, price in zip(names, qtys, prices):
            if name.strip():
                item = InvoiceItem(invoice_id=invoice.id, name=name.strip(),
                                   qty=int(qty), price=float(price))
                db.session.add(item)
        db.session.commit()
        flash("Invoice created successfully!", "success")
        return redirect(url_for('index'))
    return render_template('new_invoice.html')

@app.route('/invoice/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == 'POST':
        invoice.client_name = request.form.get('client_name', '').strip()
        invoice.tax_rate = float(request.form.get('tax_rate', 0))
        invoice.discount_rate = float(request.form.get('discount_rate', 0))

        InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
        names = request.form.getlist('item_name[]')
        qtys = request.form.getlist('item_qty[]')
        prices = request.form.getlist('item_price[]')
        for name, qty, price in zip(names, qtys, prices):
            if name.strip():
                item = InvoiceItem(invoice_id=invoice.id, name=name.strip(),
                                   qty=int(qty), price=float(price))
                db.session.add(item)
        db.session.commit()
        flash("Invoice updated successfully!", "success")
        return redirect(url_for('index'))
    return render_template('edit_invoice.html', invoice=invoice)

@app.route('/invoice/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted successfully!", "success")
    return redirect(url_for('index'))

@app.route('/invoice/<int:invoice_id>/view')
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('view_invoice.html', invoice=invoice)

# --- Excel Export ---
@app.route('/invoice/<int:invoice_id>/excel')
@login_required
def export_excel(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Invoice {invoice.id}"

    ws.append([COMPANY['name']])
    ws.append([COMPANY['address']])
    ws.append([COMPANY['phone']])
    ws.append([])
    ws.append([f"Invoice #{invoice.id}", f"Date: {invoice.date_created.strftime('%Y-%m-%d')}"])
    ws.append([])

    ws.append(['Item', 'Qty', 'Price', 'Subtotal'])
    for item in invoice.items:
        ws.append([item.name, item.qty, item.price, item.qty * item.price])

    subtotal, tax_amount, discount_amount, total = calculate_invoice_totals(invoice)
    ws.append([])
    ws.append(['', '', 'Subtotal', subtotal])
    ws.append(['', '', f'Tax ({invoice.tax_rate}%)', tax_amount])
    ws.append(['', '', f'Discount ({invoice.discount_rate}%)', discount_amount])
    ws.append(['', '', 'Total', total])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name=f"invoice_{invoice.id}.xlsx",
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- PDF Export (Print-ready, dynamic height) ---
@app.route('/invoice/<int:invoice_id>/pdf')
@login_required
def export_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    buffer = io.BytesIO()

    page_width = 420  # half of A4 width
    line_height = 18
    top_margin = 30
    bottom_margin = 40
    header_height = 120
    totals_height = 90

    page_height = top_margin + header_height + len(invoice.items)*line_height + totals_height + bottom_margin

    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    y = page_height - top_margin

    # --- Company Info ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(10, y, COMPANY['name'])
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(10, y, COMPANY['address'])
    y -= 14
    c.drawString(10, y, COMPANY['phone'])
    y -= 25

    # --- Invoice Info ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(10, y, f"Invoice #{invoice.id}")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(10, y, f"Date: {invoice.date_created.strftime('%Y-%m-%d')}")
    y -= 25

    # --- Table Header ---
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10, y, "Item")
    c.drawRightString(250, y, "Qty")
    c.drawRightString(320, y, "Price")
    c.drawRightString(410, y, "Total")
    y -= line_height
    c.setFont("Helvetica", 10)

    # --- Items ---
    for item in invoice.items:
        c.drawString(10, y, item.name[:30])
        c.drawRightString(250, y, str(item.qty))
        c.drawRightString(320, y, f"{item.price:.2f}")
        c.drawRightString(410, y, f"{item.qty * item.price:.2f}")
        y -= line_height

    # --- Totals ---
    subtotal, tax_amount, discount_amount, total = calculate_invoice_totals(invoice)
    y -= 15
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(320, y, "Subtotal:")
    c.drawRightString(410, y, f"{subtotal:.2f}")
    y -= line_height
    c.drawRightString(320, y, f"Tax ({invoice.tax_rate}%):")
    c.drawRightString(410, y, f"{tax_amount:.2f}")
    y -= line_height
    c.drawRightString(320, y, f"Discount ({invoice.discount_rate}%):")
    c.drawRightString(410, y, f"{discount_amount:.2f}")
    y -= line_height
    c.drawRightString(320, y, "Total:")
    c.drawRightString(410, y, f"{total:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"invoice_{invoice.id}.pdf",
        mimetype='application/pdf'
    )

# --- Initialize DB and default user ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="IhArmayau").first():
        hashed = bcrypt.generate_password_hash("H4b!b0Ar").decode('utf-8')
        user = User(username="IhArmayau", password_hash=hashed)
        db.session.add(user)
        db.session.commit()
        logging.info("Default user created.")

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
