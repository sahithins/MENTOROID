from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file, jsonify
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_admin import Admin
from flask_admin.contrib.mongoengine import ModelView
from models import db, User, Content, Mentor, Courses, Enrollment, Feedbacks
from functools import wraps
import secrets, os, sys, zipfile, subprocess
from werkzeug.utils import secure_filename
from forms import LoginForm
import numpy as np
from markupsafe import Markup
from datetime import datetime, timedelta

try:
    from flask_bcrypt import Bcrypt
except ImportError:
    print("some_library is not installed. Installing now...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask-Bcrypt'])
    from flask_bcrypt import Bcrypt

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] != role:
                return ('''<div class='centered block' style='padding-top: 40px; text-align: center; margin:auto;'>
                                <div>
                                    <h2>Access Denied: You do not have permission to access this page.</h2>
                                </div>
                            </div>''')
            return f(*args, **kwargs)
        return decorated_function
    return decorator

app = Flask(__name__)
bcrypt = Bcrypt(app)

app.config["SECRET_KEY"] = secrets.token_hex(21)
csrf = CSRFProtect(app)
app.config["MONGODB_SETTINGS"] = {
                                'db': 'Mentoroid',  # Use the database name you want
                                'host': 'localhost',
                                'port': 27017
                            }
app.config["MONGO_TRACK_MODIFICATIONS"] = False

app.config['UPLOAD_FOLDER'] = 'static/uploads' 
app.config['UPLOAD_FOLDER_1'] = 'static/mentor_uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_1'], exist_ok=True)

# Initialize MongoEngine
db.init_app(app)

# Initialize Flask-Admin
admin = Admin(app, name='My Admin', template_mode='bootstrap3')

class SecureModelView(ModelView):
    def is_accessible(self):
        if 'is_admin' in session and session['is_admin'] == 'admin':
            return True

    def inaccessible_callback(self, name, **kwargs):
        return ('''<div class='centered block' style='padding-top: 40px; text-align: center; margin:auto;'>
                        <div>
                            <h2>Access Denied: You do not have permission to access this page.</h2>
                        </div>
                    </div>''')

class MentorModelView(SecureModelView):
    column_list = ('fullname', 'email', 'phonenumber', 'image_file', 'qualification', 'experience', 'linkedin', 'resume_file', 'status')

    def _resume_file_formatter(view, context, model, name):
        if model.resume_file:
            return Markup(f'''<a class='btn btn-primary' href="/Download?filename={model.get_resume_url()}">Resume</a>''')
        return 'No file'
    
    def _linkedin_formatter(view, context, model, name):
        if model.linkedin:
            return Markup(f'''<a class='btn btn-primary' href="{model.linkedin}" target="__blank">Linkedin Link</a>''')
        return 'No link'

    column_formatters = {
        'resume_file': _resume_file_formatter,
        'linkedin': _linkedin_formatter,
    }

# Add views for your models
admin.add_view(SecureModelView(User))
admin.add_view(MentorModelView(Mentor))
admin.add_view(SecureModelView(Content))
admin.add_view(SecureModelView(Courses))
admin.add_view(SecureModelView(Enrollment))
admin.add_view(SecureModelView(Feedbacks))

RANDOM_COLOR = f"rgb({np.random.randint(100,180)}, {np.random.randint(100,180)}, {np.random.randint(100,180)})"
course_categories = ['IT & Software Development', 'Data Science & AI', 'Business & Finance', 'Marketing & Sales', 
                         'Graphic Design & Multimedia', 'Engineering & Architecture', 'Health & Medicine', 
                         'Language & Communication', 'Personal Development']


@app.before_request
def before_request():
    if not hasattr(app, 'enrollment_status_updated'):
        Enrollment.update_enrollment_status()
        app.enrollment_status_updated = True

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('CSRF token is missing or invalid.', 'error')
    if request.endpoint == 'mentor_dashboard':
        return redirect(url_for('mentor_dashboard'))
    if request.endpoint == 'mentor':
        return redirect(url_for('mentor'))

# ------- Non decorative functions --------
def get_enrolled_details():
    '''
    If mentor logged in then returns a list of dictionary items having key = user fullname and value = user_email
    if user logged in then returns a list of enrolled course names for a perticular user
    '''
    if 'user_email' in session and session['user_email'] != '':
        user = User.objects(email=session['user_email']).first()
        enrolled_user = Enrollment.objects(user_id=str(user.id))
        enrolled_dates = []
        enrolled_courses = []
        for i in enrolled_user:
            course = Courses.objects(id=i.course_id).first()
            enrolled_courses.append(course.course_name)
            enrolled_dates.append({'Course Name': course.course_name,'Enrollment Date': i.enrollment_date, 'Expiration Date': i.expire_date})

        return enrolled_courses, enrolled_dates

    if 'mentor_email' in session and session['mentor_email'] != '':
        enrolled_user_ids = set()
        enrolled_users = []
        enrolled_emails = []
        mentor_courses = Courses.objects(mentor_email=session['mentor_email'])
        for i in mentor_courses:
            enrolled = Enrollment.objects(course_id=str(i.id))
            enrolled_user_ids.update([ obj.user_id for obj in enrolled ])
        for i in enrolled_user_ids:
            user = User.objects(id=i).first()
            user = User.objects(email=user.email).first()
            enrolled_user = Enrollment.objects(user_id=str(user.id))
            enrolled_courses = []
            for i in enrolled_user:
                course = Courses.objects(id=i.course_id).first()
                enrolled_courses.append(course.course_name)
            enrolled_users.append({'User Name': user.fullname, 'Email': user.email, 'Enrolled Courses': ', '.join(enrolled_courses)})

        return enrolled_users
    


# -------- Actual Web Application routes starts here -----------
@app.route("/")
@app.route("/Home")
def home():
    session.pop('user_logged_in', None)
    session.pop('mentor_logged_in', None)
    session.clear()
    return render_template("Home_Page.html", title="Home Page")

@app.route("/About")
def about():
    session.pop('user_logged_in', None)
    session.pop('mentor_logged_in', None)
    session.clear()
    return render_template("About_Page.html", title="About Page")

@app.route("/Register", methods=["GET", "POST"])
def register():
    session.pop('user_loggged_in', None)
    session.pop('mentor_logged_in', None)
    if request.method == "POST":
        role = request.form['role']
        fullname = request.form['fullname']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        try:
            age = request.form['age']
            address = request.form['address']
        except:
            pass
        if role == 'Mentor':
            qualification = request.form['qualification']
            experience = request.form['experience']
            linkedin = request.form['linkedin']
        phonenumber = request.form['phonenumber']
        email = request.form['email']
        
        
        if 'imagefile' not in request.files:
            flash('No file part')
            return redirect(url_for('register'))

        if role == "User":
            existing_user = User.objects(email=email).first()  # Query for existing user
            if existing_user:
                flash('Email already exists. Please choose a different email.', 'info')
                return redirect(url_for('register'))
        else:
            existing_mentor = Mentor.objects(email=email).first()  # Query for existing mentor
            if existing_mentor:
                flash('Email already exists. Please choose a different email.', 'info')
                return redirect(url_for('register'))
            if 'resume' not in request.files:
                flash('No file part')
                return redirect(url_for('register'))
            resume_file = request.files['resume']
            if resume_file:
                resume_filename = secure_filename(resume_file.filename)
                resume_file_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_filename)
                resume_file.save(resume_file_path)

        file = request.files['imagefile']
        if file.filename == '':
            filename = "default.jpg"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

        if role == 'User':
            new_user = User(
                fullname=fullname,
                password=hashed_password,
                age=age,
                phonenumber=phonenumber,
                email=email,
                address=address,
                image_file=file_path
            )
            new_user.save()  # Save the user to MongoDB
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        if role == 'Mentor':
            new_mentor = Mentor(
                fullname=fullname,
                password=hashed_password,
                phonenumber=phonenumber,
                email=email,
                image_file=file_path,
                qualification=qualification,
                experience=experience,
                linkedin=linkedin,
                resume_file=resume_file_path
            )
            new_mentor.save()  # Save the user to MongoDB
            flash('Registration successful! Admin will validate and get back to you.', 'success')
            return redirect(url_for('mentor'))
        else:
            flash(f'Invalid form data{role}', 'danger')
            render_template("Register_Page.html", title="Register Page")

    return render_template("Register_Page.html", title="Register Page")

# ---------- user routes ----------

@app.route("/User_Login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.objects(email=form.email.data).first()  # Query for user
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            session.pop('role', None)
            session['is_admin'] = user.role
            session['role'] = 'user'
            session['user_logged_in'] = True  # Set session variable
            session['user_email'] = user.email
            session['user_name'] = user.fullname
            session['profile_picture'] = user.image_file
            flash("Login Successful", "success")
            return redirect("/User_Dashboard")
        else:
            flash("Login failed! Please check the Email and Password.", "danger")
    return render_template("User_Login_Page.html", title="User_Login Page", form=form)

@app.route("/User_Dashboard")
@role_required('user')
def user_dashboard():
    session.pop('search_materials', None)
    session.pop('search_item', None)
    enrolled_courses, _ = get_enrolled_details()
    
    # Fetch actual courses from database
    all_courses = Courses.objects.all()  # This returns queryset (iterable)
    
    return render_template(
        "User_Dashboard.html", 
        title="User Dashboard", 
        courses=all_courses,  # Pass queried results
        np=np.random,
        enrolled_courses=enrolled_courses
    )

@app.route("/User_Profile", methods = ['GET', 'POST'])
@role_required('user')
def profile():
    user = User.objects(email=session['user_email']).first()
    if request.method == 'POST':
        new_fullname = request.form.get('name')
        new_age = request.form.get('age')
        new_phonenumber = request.form.get('phonenumber')
        new_address = request.form.get('address')
        # Check if a new profile picture is being uploaded
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                user.image_file = file_path  # Update the user's profile picture field
                session['profile_picture'] = file_path

        user.fullname = new_fullname
        user.age = int(new_age) if new_age.isdigit() else None
        user.phonenumber = new_phonenumber
        user.address = new_address
        user.save()

        # flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template("User_Profile.html", title = "User Profile", user=user)

@app.route("/User_Materials")
@role_required('user')
def user_materials():
    enrolled_courses, _ = get_enrolled_details()
    return render_template("User_Materials.html", title = "User Materials", courses=Courses, enrolled_courses=enrolled_courses)

@app.route('/My_Courses')
@role_required('user')
def my_courses():
    enrolled_courses, enrolled_dates = get_enrolled_details()
    for i in enrolled_dates:
        course = Courses.objects(course_name=i['Course Name']).first()
        mentor_email = course.mentor_email
        mentor = Mentor.objects(email=mentor_email).first()
        i['Mentor Name'] = mentor.fullname
    return render_template('User_Courses.html', title='User Courses', enroll_details=enrolled_dates)

@app.route("/Feedback", methods=["GET", "POST"])
@role_required('user')
def feedback():
    if request.method == "POST":
        # Get course category from the selected course
        course_name = request.form['coursename']
        course = Courses.objects(course_name=course_name).first()
        
        new_feedback = Feedbacks(
            user_name=request.form['username'],
            user_email=session['user_email'],
            mentor_name=request.form['mentorname'],
            course_name=course_name,
            course_category=course.course_category,  # Add this line
            rating=int(request.form['rating']),
            feedback=request.form['feedback'],
            suggestions=request.form['suggestions']
        )
        new_feedback.save()
        # ... rest of your code ...
        flash('Thank you for your feedback! Your insights are invaluable to us.', 'info')
        return redirect(url_for('user_dashboard'))
    return render_template("Feedback_Page.html", title="Feedback", courses=Courses, mentors=Mentor)

@app.route('/search')
def search():
    if request.args.get('search'):
        search_term = request.args.get('search')
        session['search_item'] = search_term
        search_results = Courses.objects(course_name__icontains=search_term)
        enrolled_courses, _ = get_enrolled_details()
        return render_template("User_Dashboard.html", title = "User Dashboard", courses=search_results, np = np.random, enrolled_courses=enrolled_courses)
    
    if request.args.get('query1'):
        course_name = request.args.get('query1')
        enrolled_courses, _ = get_enrolled_details()
        if request.args.get('query2'):
            file_type = request.args.get('query2')
            session['search_content'] = file_type
            search_results = Content.objects(course_name__icontains=course_name, file_type__icontains = file_type)
            return render_template("User_Materials.html", title = "User Materials", courses=Courses, contents=search_results, enrolled_courses=enrolled_courses)
        else:
            search_results = Content.objects(course_name__icontains=course_name)
            return render_template("User_Materials.html", title = "User Materials", courses=Courses, contents=search_results, enrolled_courses=enrolled_courses)
    else:
        return redirect(url_for('user_materials'))

@app.route("/Enroll", methods = ["GET", "POST"])
@role_required('user')
def enroll():
    if request.method == "POST":
            course_name = request.args.get('coursename')
            course = Courses.objects(course_name = course_name).first()
            course_id = str(course.id)
            user = User.objects(email = session['user_email']).first()
            user_id = str(user.id)
            new_enrollment = Enrollment(user_id=user_id, course_id=course_id, expire_date=datetime.utcnow() + timedelta(days=90))
            new_enrollment.save()
            flash(f"{course_name} Enrolled successfully!😃", 'success')
            return redirect('/User_Dashboard')
    if request.args.get('coursename'):
        course_name = request.args.get('coursename')
        course = Courses.objects(course_name=course_name).first()
        return render_template("Enroll.html", title = 'Enroll Page', course = course)

@app.route("/Logout")
def logout():
    session.pop('user_logged_in', None)  # Removes the session variable
    session.pop('user_email', None)  # Optionally removes user email
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

# --------- Mentor routs ----------

@app.route("/Mentor_Login", methods=["GET", "POST"])
def mentor():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        mentor = Mentor.objects(email=email).first()
        if mentor and bcrypt.check_password_hash(mentor.password, password):
            if mentor.status:
                session.pop('role', None)
                session['role'] = 'mentor'
                session['mentor_logged_in'] = True  # Sets session variable
                session['mentor_name'] = mentor.fullname
                session['mentor_email'] = email
                session['profile_picture'] = mentor.image_file
                flash("Login Successful", "success")
                return redirect("/Mentor_Course_Manager")
            else:
                flash("Your account is not active. Please contact admin.", "danger")
        else:
            flash("Login failed! Please check the Email and Password.", "danger")
            return redirect("/Mentor_Login")
    return render_template("Mentor_Login_Page.html", title = "Mentor Login")

@app.route("/Mentor_Course_Manager", methods=["GET", "POST"])
@role_required('mentor')
def mentor_course_manager():
    if request.method == "POST":
        course_name = request.form['coursename']
        try:
            file_type = request.form['contenttype']
        except:
            summary = request.form['summary']
            course_category = request.form['coursecategory']
            if 'imagefile' not in request.files:
                flash('No file part')
                return render_template("Mentor_Course_Manager.html", title="Mentor Course Manager", courses=Courses.objects(mentor_email=session['mentor_email']), categories=course_categories)
            file = request.files['imagefile']
        else:
            title = request.form['title']
            description = request.form['description']
            if 'file' not in request.files:
                flash('No file part')
                return render_template("Mentor_Course_Manager.html", title="Mentor Course Manager", courses=Courses.objects(mentor_email=session['mentor_email']), categories=course_categories)
            file = request.files['file']

        if file.filename == '':
            flash('No selected file')
            return render_template("Mentor_Course_Manager.html", title="Mentor Course Manager", courses=Courses.objects(mentor_email=session['mentor_email']), categories=course_categories)
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename)
            file.save(file_path)
    
        try:
            new_content = Content(
                course_name=course_name,
                title=title,
                file_type=file_type,
                description=description,
                upload_file=file_path
            )
            new_content.save()
            flash('Upload successful!', 'success')
            return render_template(
                "Mentor_Course_Manager.html", 
                title="Mentor Course Manager", 
                courses=Courses.objects(mentor_email=session['mentor_email']), 
                categories=course_categories
            )
        except:
            new_course = Courses(
                course_name=course_name,
                course_category=course_category,
                mentor_email=session['mentor_email'],
                summary=summary,
                course_image=file_path
            )
            new_course.save()
            flash('New course added successfully!', 'success')
            return render_template(
                "Mentor_Course_Manager.html", 
                title="Mentor Course Manager", 
                courses=Courses.objects(mentor_email=session['mentor_email']), 
                categories=course_categories
            )

    return render_template(
        "Mentor_Course_Manager.html", 
        title="Mentor Course Manager", 
        courses=Courses.objects(mentor_email=session['mentor_email']), 
        categories=course_categories
    )

@app.route("/Content_Upload", methods = ["GET", "POST"])
@role_required('mentor')
def content_upload():
    course = request.args.get('course')
    contents = Content.objects(course_name=course) # getting all materials uploaded in this course
    if request.method == "POST":
        file_type = request.form['contenttype']
        title = request.form['title']
        description = request.form['description']
        
        if 'file' not in request.files:
            flash('No file part')
            return render_template("Content_Upload.html", title = "Content Upload", courses=Courses, course=course)

        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return render_template("Content_Upload.html", title = "Content Upload", courses=Courses, course=course)

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename)
            file.save(file_path)

            new_content = Content(
                course_name=course,
                file_type=file_type,
                title=title,
                description=description,
                upload_file=file_path
            )
            new_content.save()  # Save the user to MongoDB
            flash('Upload successful!', 'success')
            
            return render_template("Content_Upload.html", title = "Content Upload", courses=Courses, course=course, contents=contents)

    return render_template("Content_Upload.html", title = "Content Upload", courses=Courses, course=course, contents=contents)

@app.route("/Mentor_Dashboard", methods=["GET", "POST"])
@role_required('mentor')
def mentor_dashboard():
    courses = Courses.objects(mentor_email=session['mentor_email'])
    if request.method == 'POST':
        selected_category = request.form['coursecategory']
        if selected_category != '0':
            courses = Courses.objects(course_category=selected_category, mentor_email=session['mentor_email'])
            return render_template("Mentor_Dashboard.html", title="Mentor Dashboard", courses=courses, content=Content, categories=course_categories)
        else:
            courses = Courses.objects(mentor_email=session['mentor_email'])
            return render_template("Mentor_Dashboard.html", title="Mentor Dashboard", courses=courses, content=Content, categories=course_categories)
    return render_template("Mentor_Dashboard.html", title="Mentor Dashboard", courses=courses, content=Content, categories=course_categories)
        
            
@app.route("/Enrolled_Users")
@role_required('mentor')
def enrolled_users():
    enrolled_users = get_enrolled_details()
    return render_template('Enrolled_Users.html', title = "Enrolled Users", enrolled_users=enrolled_users)

@app.route("/View_Feedback")
@role_required('mentor')
def view_feedback():
    grouped_feedbacks = {}
    for category in course_categories:
        # Use the correct field name from Feedbacks model
        category_feedbacks = Feedbacks.objects(course_category=category)
        if category_feedbacks:
            grouped_feedbacks[category] = category_feedbacks
            
    return render_template('View_Feedback.html',
        grouped_feedbacks=grouped_feedbacks,
        categories=course_categories
    )

@app.route("/Mentor_Logout")
def mentor_logout():
    session.pop('mentor_logged_in', None)  # Removes the session variable
    session.pop('mentor_email', None)  # Optionally removes mentor email
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

# --------- Download routes -----------
@app.route('/Download', methods=['GET'])
def download_file():
    filename = request.args.get('filename')
    if os.path.exists(filename):
        return send_file(filename, as_attachment=True)
    else:
        return "File not found", 404

@app.route('/download_zip')
def download_zip():
    # Get the list of files to download from the query parameters
    files_to_download = request.args.getlist('files')  # Expecting a list of file names

    zip_filename = 'filtered_materials.zip'
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for file_name in files_to_download:
            if os.path.exists(file_name):
                zipf.write(file_name, os.path.basename(file_name))
            else:
                return f"File not found {file_name}", 404

    return send_file(zip_filename, as_attachment=True)

if __name__ == "__main__":
    app.run(port=5000, debug=True)