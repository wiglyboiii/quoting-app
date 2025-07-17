# A tiny change to trigger a new deployment
# The special code block MUST be the very first thing in the file.
import os
import sys
if getattr(sys, 'frozen', False):
    gtk_path = 'C:\\Program Files\\GTK3-Runtime Win64\\bin'
    if os.path.exists(gtk_path):
        os.environ['PATH'] = gtk_path + os.pathsep + os.environ.get('PATH', '')

from flask import Flask, render_template, request, redirect, url_for, make_response, flash, jsonify
from sqlalchemy.exc import IntegrityError
from flask_sqlalchemy import SQLAlchemy
from weasyprint import HTML
from werkzeug.utils import secure_filename
import datetime
import webbrowser

# --- (Setup) ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'projects.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'a-super-secret-key-that-you-should-change'
db = SQLAlchemy(app)

# --- (Database Models) ---
class Setting(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=True)

    def to_dict(self):
        return { 'key': self.key, 'value': self.value }

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    project_name = db.Column(db.String(100), nullable=False)
    client_name = db.Column(db.String(100))
    client_address = db.Column(db.String(300), nullable=True)
    project_description = db.Column(db.Text)
    price_adjustment = db.Column(db.Float, nullable=False, default=0.0)
    proposed_start_date = db.Column(db.String(100), nullable=True)
    job_duration = db.Column(db.String(100), nullable=True)
    materials = db.relationship('ProjectMaterial', backref='project', lazy=True, cascade="all, delete-orphan")

    def to_dict_simple(self):
        # A simple version for lists, without all the details
        return {
            'id': self.id,
            'quote_number': self.quote_number,
            'project_name': self.project_name,
            'client_name': self.client_name,
        }
    
    def to_dict_detailed(self):
        # A detailed version for the single project view
        materials_list = [item.to_dict() for item in self.materials]
        
        # Calculate totals
        subtotal = 0
        gst_base = 0
        for item in self.materials:
            base_price = item.quantity * item.material.price
            marked_up_price = base_price * (1 + item.markup_percentage / 100.0)
            subtotal += marked_up_price
            if item.gst_applied:
                gst_base += marked_up_price
        
        gst_amount = gst_base * 0.15
        grand_total = (subtotal + gst_amount) + self.price_adjustment

        return {
            'id': self.id,
            'quote_number': self.quote_number,
            'project_name': self.project_name,
            'client_name': self.client_name,
            'client_address': self.client_address,
            'project_description': self.project_description,
            'price_adjustment': self.price_adjustment,
            'proposed_start_date': self.proposed_start_date,
            'job_duration': self.job_duration,
            'materials': materials_list,
            'totals': {
                'subtotal': round(subtotal, 2),
                'gst_amount': round(gst_amount, 2),
                'grand_total': round(grand_total, 2)
            }
        }

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_name = db.Column(db.String(100), nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)
    product_url = db.Column(db.String(500), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'material_name': self.material_name,
            'price': self.price,
            'product_url': self.product_url
        }

class ProjectMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    gst_applied = db.Column(db.Boolean, default=False, nullable=False)
    markup_percentage = db.Column(db.Integer, nullable=False, default=0)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    material = db.relationship('Material', backref='project_links', lazy=True)

    def to_dict(self):
        # Includes details from the linked material model
        return {
            'id': self.id,
            'quantity': self.quantity,
            'gst_applied': self.gst_applied,
            'markup_percentage': self.markup_percentage,
            'material_id': self.material_id,
            'material_name': self.material.material_name,
            'material_price': self.material.price
        }

# --- (API Routes for Android App) ---
@app.route('/api/projects', methods=['GET'])
def api_get_projects():
    all_projects = Project.query.order_by(Project.id.desc()).all()
    projects_list = [project.to_dict_simple() for project in all_projects]
    return jsonify(projects_list)

@app.route('/api/projects/<int:project_id>', methods=['GET'])
def api_get_project_details(project_id):
    project = Project.query.get_or_404(project_id)
    return jsonify(project.to_dict_detailed())

@app.route('/api/materials', methods=['GET'])
def api_get_materials():
    all_materials = Material.query.all()
    materials_list = [material.to_dict() for material in all_materials]
    return jsonify(materials_list)

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    settings_list = Setting.query.all()
    settings_dict = {s.key: s.value for s in settings_list}
    return jsonify(settings_dict)

# --- (Original Web App Routes) ---
@app.route('/settings')
def settings():
    settings_list = Setting.query.all()
    settings = {s.key: s.value for s in settings_list}
    return render_template('settings.html', settings=settings)
@app.route('/settings/update', methods=['POST'])
def update_settings():
    settings_keys = ['company_name', 'company_address', 'company_phone', 'company_email', 'payment_details', 'quote_notes']
    for key in settings_keys:
        setting = Setting.query.get(key)
        if not setting: setting = Setting(key=key); db.session.add(setting)
        setting.value = request.form.get(key)
    logo_file = request.files.get('company_logo')
    if logo_file and logo_file.filename != '':
        filename = secure_filename(logo_file.filename)
        upload_folder = os.path.join(app.root_path, 'static', 'uploads'); os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, filename); logo_file.save(save_path)
        logo_path_setting = Setting.query.get('company_logo_path')
        if not logo_path_setting: logo_path_setting = Setting(key='company_logo_path'); db.session.add(logo_path_setting)
        logo_path_setting.value = os.path.join('uploads', filename).replace("\\", "/")
    db.session.commit(); flash('Settings updated successfully!', 'success'); return redirect(url_for('settings'))
@app.route('/')
def index():
    all_projects = Project.query.order_by(Project.id.desc()).all()
    return render_template('index.html', projects=all_projects)
@app.route('/add', methods=['POST'])
def add_project():
    new_project = Project(
        quote_number=request.form.get('quote_number'),
        project_name=request.form.get('project_name'), 
        client_name=request.form.get('client_name'), 
        client_address=request.form.get('client_address'),
        proposed_start_date=request.form.get('proposed_start_date'),
        job_duration=request.form.get('job_duration'),
        project_description=request.form.get('project_description')
    )
    db.session.add(new_project); db.session.commit(); return redirect(url_for('index'))
@app.route('/project/edit/<int:project_id>')
def edit_project(project_id):
    project_to_edit = Project.query.get_or_404(project_id)
    return render_template('edit_project.html', project=project_to_edit)
@app.route('/project/update/<int:project_id>', methods=['POST'])
def update_project(project_id):
    project_to_update = Project.query.get_or_404(project_id)
    project_to_update.quote_number = request.form.get('quote_number')
    project_to_update.project_name = request.form.get('project_name')
    project_to_update.client_name = request.form.get('client_name')
    project_to_update.client_address = request.form.get('client_address')
    project_to_update.proposed_start_date = request.form.get('proposed_start_date')
    project_to_update.job_duration = request.form.get('job_duration')
    project_to_update.project_description = request.form.get('project_description')
    try:
        db.session.commit()
        flash('Project updated successfully.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f"Error: Quote number '{project_to_update.quote_number}' is already in use. Please choose a unique quote number.", 'error')
    return redirect(url_for('index'))
@app.route('/project/delete/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    project_to_delete = Project.query.get_or_404(project_id); db.session.delete(project_to_delete); db.session.commit(); return redirect(url_for('index'))
@app.route('/materials')
def materials():
    all_materials = Material.query.all()
    return render_template('materials.html', materials=all_materials)
@app.route('/add_material', methods=['POST'])
def add_material():
    new_material = Material(material_name=request.form.get('material_name'), price=float(request.form.get('price')), product_url=request.form.get('product_url'))
    db.session.add(new_material)
    try:
        db.session.commit()
        flash(f"Successfully added material: {new_material.material_name}", 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f"Error: A material named '{new_material.material_name}' already exists.", 'error')
    return redirect(url_for('materials'))
@app.route('/material/edit/<int:material_id>')
def edit_material(material_id):
    material_to_edit = Material.query.get_or_404(material_id)
    return render_template('edit_material.html', material=material_to_edit)
@app.route('/material/update/<int:material_id>', methods=['POST'])
def update_material(material_id):
    material_to_update = Material.query.get_or_404(material_id)
    material_to_update.material_name = request.form.get('material_name'); material_to_update.price = float(request.form.get('price')); material_to_update.product_url = request.form.get('product_url')
    db.session.commit(); return redirect(url_for('materials'))
@app.route('/project/<int:project_id>')
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    all_materials = Material.query.all()
    calculated_total = 0
    for item in project.materials:
        base_price = item.quantity * item.material.price
        marked_up_price = base_price * (1 + item.markup_percentage / 100.0)
        line_total = marked_up_price
        if item.gst_applied:
            line_total *= 1.15
        calculated_total += line_total
    final_total = calculated_total + project.price_adjustment
    return render_template('project.html', project=project, all_materials=all_materials, calculated_total=calculated_total, final_total=final_total)
@app.route('/project/adjust_price/<int:project_id>', methods=['POST'])
def adjust_price(project_id):
    project = Project.query.get_or_404(project_id)
    adjustment = request.form.get('price_adjustment', 0.0, type=float)
    project.price_adjustment = adjustment
    db.session.commit()
    flash('Final price has been adjusted.', 'success')
    return redirect(url_for('view_project', project_id=project.id))
@app.route('/project/<int:project_id>/add_material', methods=['POST'])
def add_material_to_project(project_id):
    markup = request.form.get('markup_percentage', 0, type=int)
    new_project_material = ProjectMaterial(project_id=project_id, material_id=int(request.form.get('material_id')), quantity=int(request.form.get('quantity')), gst_applied=request.form.get('gst_toggle') == 'on', markup_percentage=markup)
    db.session.add(new_project_material); db.session.commit(); return redirect(url_for('view_project', project_id=project_id))
@app.route('/project/item/edit/<int:item_id>')
def edit_project_material(item_id):
    item_to_edit = ProjectMaterial.query.get_or_404(item_id)
    return render_template('edit_item.html', item=item_to_edit)
@app.route('/project/item/update/<int:item_id>', methods=['POST'])
def update_project_material(item_id):
    item_to_update = ProjectMaterial.query.get_or_404(item_id)
    item_to_update.quantity = int(request.form.get('quantity')); item_to_update.markup_percentage = int(request.form.get('markup_percentage')); item_to_update.gst_applied = request.form.get('gst_toggle') == 'on'
    db.session.commit(); return redirect(url_for('view_project', project_id=item_to_update.project_id))
@app.route('/project/item/delete/<int:item_id>', methods=['POST'])
def delete_project_material(item_id):
    item_to_delete = ProjectMaterial.query.get_or_404(item_id); project_id = item_to_delete.project_id; db.session.delete(item_to_delete); db.session.commit(); return redirect(url_for('view_project', project_id=project_id))
@app.route('/project/duplicate/<int:project_id>', methods=['POST'])
def duplicate_project(project_id):
    original_project = Project.query.get_or_404(project_id)
    new_project = Project(quote_number=original_project.quote_number + " (Copy)", project_name=original_project.project_name, client_name=original_project.client_name, client_address=original_project.client_address, project_description=original_project.project_description, proposed_start_date=original_project.proposed_start_date, job_duration=original_project.job_duration, price_adjustment=original_project.price_adjustment)
    for item in original_project.materials:
        new_item = ProjectMaterial(project=new_project, material_id=item.material_id, quantity=item.quantity, markup_percentage=item.markup_percentage, gst_applied=item.gst_applied)
        db.session.add(new_item)
    db.session.add(new_project); db.session.commit()
    flash(f"Successfully duplicated project. New quote number is '{new_project.quote_number}'.", 'success')
    return redirect(url_for('index'))
@app.route('/project/<int:project_id>/pdf')
def generate_pdf(project_id):
    project = Project.query.get_or_404(project_id)
    settings = {s.key: s.value for s in Setting.query.all()}
    subtotal = 0; gst_base = 0
    for item in project.materials:
        base_price = item.quantity * item.material.price
        marked_up_price = base_price * (1 + item.markup_percentage / 100.0)
        subtotal += marked_up_price
        if item.gst_applied:
            gst_base += marked_up_price
    gst_amount = gst_base * 0.15
    grand_total = (subtotal + gst_amount) + project.price_adjustment
    quote_date = datetime.date.today()
    expiry_date = quote_date + datetime.timedelta(days=14)
    rendered_html = render_template('quote_template.html', project=project, settings=settings, subtotal=subtotal, gst_amount=gst_amount, grand_total=grand_total, quote_date_str=quote_date.strftime("%d %B %Y"), expiry_date_str=expiry_date.strftime("%d %B %Y"))
    pdf = HTML(string=rendered_html).write_pdf(); response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'; response.headers['Content-Disposition'] = f'inline; filename=quote_{project.quote_number}.pdf'
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    from threading import Timer
    Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host='0.0.0.0', port=5000)