import traceback
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file, jsonify
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_admin import Admin
from flask_admin.contrib.mongoengine import ModelView
from models import CompletionStatus, Lesson, Quiz, Unit, db, User, Mentor, Courses, Enrollment, Feedbacks, Certificate, Question
from functools import wraps
import secrets, os, sys, zipfile, subprocess
from werkzeug.utils import secure_filename
from forms import LoginForm
import numpy as np
from markupsafe import Markup
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from mongoengine.errors import NotUniqueError, ValidationError, DoesNotExist
from reportlab.lib.pagesizes import letter
from mongoengine.queryset.visitor import Q

from dotenv import load_dotenv
from flask_session import Session

from chatbot import MentoroidChatbot


load_dotenv()

from reportlab.lib.units import inch

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
            # Check for user role specifically for chatbot access
            if role == 'user' and ('role' not in session or session['role'] != 'user'):
                 # For API requests, return JSON error
                 if request.endpoint == 'chat_api':
                     return jsonify({'error': 'Access Denied: User login required.'}), 403
                 # For regular page requests, return HTML error
                 return ('''<div class='centered block' style='padding-top: 40px; text-align: center; margin:auto;'>
                                <div>
                                    <h2>Access Denied: You do not have permission to access this page.</h2>
                                </div>
                            </div>''')
            # Keep original logic for other roles if needed
            elif 'role' not in session or session['role'] != role:
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
    'db': 'Mentoroid',
    'host': 'localhost',
    'port': 27017
}
app.config["MONGO_TRACK_MODIFICATIONS"] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['UPLOAD_FOLDER_1'] = 'static/mentor_uploads'
app.config['CERTIFICATES_FOLDER'] = 'static/certificates'
os.makedirs(app.config['CERTIFICATES_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_1'], exist_ok=True)


app.config["SESSION_PERMANENT"] = False # Use session cookies
app.config["SESSION_TYPE"] = "filesystem" # Store session data on the server's filesystem
app.config["SESSION_FILE_DIR"] = "./.flask_session/" # Directory to store session files
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True) # Create dir if not exists
Session(app) # Initialize session extension

# Initialize MongoEngine
db.init_app(app)

def setup_initial_admin():
    """Checks environment variables and creates an initial admin if specified and not existing."""
    admin_email = os.getenv('INITIAL_ADMIN_EMAIL')
    admin_pass = os.getenv('INITIAL_ADMIN_PASSWORD')
    admin_name = os.getenv('INITIAL_ADMIN_FULLNAME', 'Default Admin') # Provide a default name

    if admin_email and admin_pass:
        print(f"INFO: Checking for initial admin user: {admin_email}")
        existing_admin = User.objects(email=admin_email).first()

        if not existing_admin:
            print(f"INFO: Initial admin '{admin_email}' not found. Creating...")
            try:
                hashed_password = bcrypt.generate_password_hash(admin_pass).decode('utf-8')
                admin_user = User(
                    email=admin_email,
                    fullname=admin_name,
                    password=hashed_password,
                    role='admin',
                    age=0,
                    address="",
                    phonenumber=""

                )
                admin_user.save()
                print(f"SUCCESS: Initial admin user '{admin_name}' with email '{admin_email}' created.")
            except ValidationError as e:
                print(f"ERROR: Failed to create initial admin '{admin_email}'. Validation Error: {e}", file=sys.stderr)
            except NotUniqueError:
                 print(f"ERROR: Failed to create initial admin '{admin_email}'. Email already exists (race condition?).", file=sys.stderr)
            except Exception as e:
                print(f"ERROR: An unexpected error occurred during initial admin creation for '{admin_email}': {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
        else:
            print(f"INFO: Initial admin user '{admin_email}' already exists. Skipping creation.")
    else:
        pass

with app.app_context():
    setup_initial_admin()

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
admin.add_view(SecureModelView(Unit)) 
admin.add_view(SecureModelView(Lesson)) 
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
    if 'user_email' in session and session['user_email'] != '':
        user = User.objects(email=session['user_email']).first()
        if not user: return [], [] # Handle case where user might not exist

        # Use ReferenceField correctly
        enrolled_user_enrollments = Enrollment.objects(user_id=str(user.id), status='active')
        enrolled_courses_names = []
        enrolled_dates_details = []

        for enrollment in enrolled_user_enrollments:
            course = enrollment.course # Access the referenced Course object directly
            if course: # Check if course exists (it should, but good practice)
                enrolled_courses_names.append(course.course_name)
                enrolled_dates_details.append({
                    'Course Name': course.course_name,
                    'Enrollment Date': enrollment.enrollment_date,
                    'Expiration Date': enrollment.expire_date,
                    'Course ID': str(course.id) # Pass course ID if needed later
                 })
        return enrolled_courses_names, enrolled_dates_details

    if 'mentor_email' in session and session['mentor_email'] != '':
        enrolled_users_details = []
        mentor_courses = Courses.objects(mentor_email=session['mentor_email'])
        # Get all course IDs for this mentor
        mentor_course_ids = [course.id for course in mentor_courses]

        # Find all active enrollments for these courses
        enrollments = Enrollment.objects(course__in=mentor_course_ids, status='active')

        # Get unique user IDs from these enrollments
        user_ids = set(enr.user_id for enr in enrollments)

        # Fetch user details and their enrolled courses (specific to this mentor)
        for user_id in user_ids:
            user = User.objects(id=user_id).first()
            if user:
                # Find which of the mentor's courses this user is enrolled in
                user_enrollments_for_mentor_courses = Enrollment.objects(user_id=user_id, course__in=mentor_course_ids, status='active')
                enrolled_course_names_for_user = [enr.course.course_name for enr in user_enrollments_for_mentor_courses if enr.course]

                enrolled_users_details.append({
                    'User Name': user.fullname,
                    'Email': user.email,
                    'Enrolled Courses': ', '.join(enrolled_course_names_for_user) # Courses taught by THIS mentor
                })
        return enrolled_users_details

    return [], [] # Default return if no one is logged in properly


def get_chatbot_instance():
    # You might cache this instance per request using Flask's g object if needed
    # For now, create a new one each time to ensure fresh memory context starts cleanly
    # If using shared instance: need to load/save/clear memory based on session['user_email']
    return MentoroidChatbot()

# -------- Actual Web Application routes starts here -----------
@app.route("/")
@app.route("/Home")
def home():
    session.pop('user_logged_in', None)
    session.pop('mentor_logged_in', None)
    session.clear()
    return render_template("Home_Page.html", title="Home Page")



@app.route('/View', methods=['GET'])

def view_file():

    import os

    rel_path = request.args.get('filename')

    if not rel_path:

        return "No file specified", 400



    # Ensure there is a slash after "static/mentor_uploads"

    prefix = "static/mentor_uploads"

    if rel_path.startswith(prefix) and not rel_path[len(prefix):].startswith('/'):

        rel_path = prefix + '/' + rel_path[len(prefix):]



    # Normalize the path separator for Windows

    rel_path = rel_path.replace('/', os.sep)



    # Build the absolute path

    absolute_path = os.path.join(app.root_path, rel_path)

    print("Computed absolute path:", absolute_path)  # Debug output



    if os.path.exists(absolute_path):

        return send_file(absolute_path, as_attachment=False)

    else:

        return f"File not found: {absolute_path}", 404


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
    # ... (Keep existing user_dashboard, check course fetching if needed) ...
    # Fetching all courses remains the same here
    session.pop('search_materials', None)
    session.pop('search_item', None)
    enrolled_courses_names, _ = get_enrolled_details()
    all_courses = Courses.objects.all()
    for course in all_courses:
        r = np.random.randint(150, 255)
        g = np.random.randint(150, 255)
        b = np.random.randint(150, 255)
        course.random_color = "#{:02x}{:02x}{:02x}".format(r, g, b)

    if 'chat_history' not in session:
        session['chat_history'] = []
    return render_template(
        "User_Dashboard.html",
        title="User Dashboard",
        courses=all_courses,
        np=np.random,
        enrolled_courses=enrolled_courses_names,
        chat_history=session.get('chat_history', [])
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
                user.image_file = file_path 
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
    enrolled_courses_names, enrolled_dates_details = get_enrolled_details()
    selected_course_id = request.args.get('course_id')
    course_structure = {}
    selected_course_obj = None
    all_lessons_count = 0
    quiz = None # <<< Initialize quiz variable
    completion_status = None # <<< Initialize completion_status

    # *** Initialize variables BEFORE the conditional block ***
    completed_lesson_ids = set()
    completed_lessons_count = 0
    completion_percentage = 0
    quiz_passed = False # <<< Initialize quiz_passed
    quiz_taken = False # <<< Initialize quiz_taken

    if selected_course_id:
        user = User.objects(email=session['user_email']).first()
        try:
            selected_course_obj = Courses.objects(id=selected_course_id).first()
        except Exception:
             selected_course_obj = None
             flash("Invalid course identifier provided.", "warning")

        if user and selected_course_obj and selected_course_obj.course_name in enrolled_courses_names:
            units = Unit.objects(course=selected_course_obj).order_by('order', 'title')
            for unit in units:
                lessons = Lesson.objects(unit=unit).order_by('order', 'title')
                course_structure[unit] = list(lessons)
                all_lessons_count += len(lessons)

            # --- Get Quiz ---
            quiz = Quiz.objects(course=selected_course_obj).first() # <<< Fetch quiz here

            # --- Get Completion Status ---
            completion_status = CompletionStatus.objects(user_email=session['user_email'], course=selected_course_obj).first()
            if completion_status:
                 completed_lesson_ids = set(str(lesson.id) for lesson in completion_status.completed_lessons)
                 quiz_passed = completion_status.quiz_passed # <<< Get quiz status
                 quiz_taken = completion_status.quiz_taken   # <<< Get quiz status

            # Calculate counts and percentage
            completed_lessons_count = len(completed_lesson_ids)
            if all_lessons_count > 0:
                 completion_percentage = round((completed_lessons_count / all_lessons_count) * 100)

        elif selected_course_id:
             flash("You are not enrolled in this course or the course does not exist.", "warning")
             selected_course_id = None
             selected_course_obj = None
             quiz = None # Reset quiz if course invalid
             completion_status = None # Reset status

    # Prepare list of enrolled courses (id, name) for the dropdown
    enrolled_courses_list = []
    for detail in enrolled_dates_details:
        if detail.get('Course ID'):
            enrolled_courses_list.append({
                'id': detail.get('Course ID'),
                'name': detail.get('Course Name')
            })

    return render_template("User_Materials.html",
                           title="User Materials",
                           enrolled_courses_list=enrolled_courses_list,
                           selected_course_id=selected_course_id,
                           selected_course=selected_course_obj,
                           course_structure=course_structure,
                           completed_lesson_ids=completed_lesson_ids,
                           completion_percentage=completion_percentage,
                           all_lessons_count=all_lessons_count,
                           completed_lessons_count=completed_lessons_count,
                           quiz=quiz,  # <<< Pass quiz object to template
                           completion_status=completion_status, # <<< Pass status object
                           quiz_passed=quiz_passed, # <<< Pass quiz passed status
                           quiz_taken=quiz_taken # <<< Pass quiz taken status
                           )

@app.route('/mark_lesson_complete', methods=['POST'])
@role_required('user')
def mark_lesson_complete():
    try:
        lesson_id = request.json.get('lesson_id')
        course_id = request.json.get('course_id')
        user_email = session.get('user_email')

        # Validate data presence early
        if not all([lesson_id, course_id, user_email]):
             print("ERROR: Missing lesson_id, course_id, or user_email in request.")
             return jsonify({'success': False, 'message': 'Missing required data.'}), 400

        # Fetch lesson and course with specific error handling
        try:
            lesson = Lesson.objects(id=lesson_id).first()
            course = Courses.objects(id=course_id).first()
        except (ValidationError) as e: # Catches invalid ObjectId format
             print(f"ERROR fetching lesson/course: Invalid ID format? {e}", file=sys.stderr)
             return jsonify({'success': False, 'message': f'Invalid lesson or course ID format: {e}'}), 400
        except Exception as e: # Catch other potential DB errors during fetch
             print(f"ERROR fetching lesson/course (Unknown): {e}", file=sys.stderr)
             traceback.print_exc(file=sys.stderr)
             return jsonify({'success': False, 'message': 'Error fetching data from database.'}), 500

        # Check if objects were found
        if not lesson or not course:
            error_msg = f"Mark Complete Error: Not found - Lesson: {lesson_id}, Course: {course_id}"
            print(error_msg)
            # Return 404 Not Found if specific items missing
            return jsonify({'success': False, 'message': 'Lesson or Course not found.'}), 404

        # --- "Get or Create" CompletionStatus ---
        try:
            completion_status = CompletionStatus.objects(user_email=user_email, course=course).first()
            if not completion_status:
                print(f"DEBUG: Creating new CompletionStatus for User: {user_email}, Course ID: {course.id}")
                completion_status = CompletionStatus(
                    user_email=user_email,
                    course=course,
                    completed_lessons=[]
                )
                completion_status.save() # save can also raise errors
                # Re-fetch to ensure we have the object from DB perspective if needed,
                # though assignment above should be sufficient if save succeeds
                completion_status = CompletionStatus.objects(id=completion_status.id).first() # Or just use the saved object

            if not completion_status: # Should not happen if save worked
                 raise Exception("Failed to retrieve completion_status after save.")

            # --- DB Update ---
            result = CompletionStatus.objects(id=completion_status.id).update_one(add_to_set__completed_lessons=lesson)

            # --- Recalculation ---
            units = Unit.objects(course=course) # Fetch units related to the course
            all_lessons_count = Lesson.objects(unit__in=units).count() # Count lessons within those units
            completion_status.reload() # Reload essential after update
            completed_lessons_count = len(completion_status.completed_lessons)
            completion_percentage = round((completed_lessons_count / all_lessons_count) * 100) if all_lessons_count > 0 else 0

            # --- Logging ---
            print(f"DEBUG: Mark Complete - User: {user_email}, Course: {course_id}, Lesson: {lesson_id}")
            print(f"DEBUG: Counts - Completed: {completed_lessons_count}, Total: {all_lessons_count}")
            print(f"DEBUG: Calculated Percentage: {completion_percentage}")

            # --- Success Return ---
            return jsonify({
                'success': True,
                'completed_count': completed_lessons_count,
                'total_count': all_lessons_count,
                'percentage': completion_percentage
            })

        except ValidationError as e: # Catch validation errors during save/update
            print(f"ERROR in /mark_lesson_complete (Validation on Save/Update): {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return jsonify({'success': False, 'message': f'Data validation error during update: {e}'}), 400
        except Exception as e: # Catch other errors during get/create/update/reload
            print(f"ERROR in /mark_lesson_complete (DB Operation): {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return jsonify({'success': False, 'message': 'Internal server error during database operation.'}), 500

    # Catch errors outside the main try (e.g., accessing request.json if content-type is wrong)
    except Exception as e:
        print(f"ERROR in /mark_lesson_complete (Outer): {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        # Determine appropriate status code (400 for bad request, 500 for others)
        status_code = 400 if isinstance(e, (TypeError, KeyError, AttributeError)) else 500
        return jsonify({'success': False, 'message': 'An error occurred processing the request.'}), status_code


@app.route('/My_Courses')
@role_required('user')
def my_courses():
    # Use the updated get_enrolled_details which returns more info
    _, enrolled_dates_details = get_enrolled_details()
    # Fetch mentor names - slightly adjusted
    for detail in enrolled_dates_details:
         course = Courses.objects(id=detail.get('Course ID')).first()
         if course and course.mentor_email:
             mentor = Mentor.objects(email=course.mentor_email).first()
             detail['Mentor Name'] = mentor.fullname if mentor else 'N/A'
         else:
              detail['Mentor Name'] = 'N/A'
    return render_template('User_Courses.html', title='User Courses', enroll_details=enrolled_dates_details)


@app.route("/Feedback", methods=["GET", "POST"])
@role_required('user')
def feedback():
    if request.method == "POST":
        
        course_name = request.form['coursename']
        course = Courses.objects(course_name=course_name).first()
        
        new_feedback = Feedbacks(
            user_name=request.form['username'],
            user_email=session['user_email'],
            mentor_name=request.form['mentorname'],
            course_name=course_name,
            course_category=course.course_category,  
            rating=int(request.form['rating']),
            feedback=request.form['feedback'],
            suggestions=request.form['suggestions']
        )
        new_feedback.save()
    
        flash('Thank you for your feedback! Your insights are valuable to us.', 'info')
        return redirect(url_for('user_dashboard'))
    return render_template("Feedback_Page.html", title="Feedback", courses=Courses, mentors=Mentor)

@app.route('/search')
def search():
     # Search Courses on Dashboard
    if request.args.get('search') and 'user_logged_in' in session:
        search_term = request.args.get('search')
        session['search_item'] = search_term
        # Search by course name OR category
        search_results = Courses.objects(Q(course_name__icontains=search_term) | Q(course_category__icontains=search_term))
        enrolled_courses_names, _ = get_enrolled_details()
        # Add random colors for display
        for course in search_results:
             r, g, b = np.random.randint(150, 255, 3)
             course.random_color = "#{:02x}{:02x}{:02x}".format(r, g, b)

        return render_template("User_Dashboard.html",
                               title="User Dashboard",
                               courses=search_results,
                               np=np.random,
                               enrolled_courses=enrolled_courses_names)

    # This part for searching within User_Materials is handled by the '/User_Materials' route itself via query param now.
    # else:
    #     # Default redirect if no specific search type recognized
    #     if 'user_logged_in' in session:
    #          return redirect(url_for('user_dashboard'))
    #     else:
    #          return redirect(url_for('home')) # Or login page

    # Fallback if accessed directly without search query
    return redirect(url_for('user_dashboard' if 'user_logged_in' in session else 'home'))

@app.route("/Enroll", methods=["GET", "POST"])
@role_required('user')
def enroll():
    if request.method == "POST":
        course_id = request.args.get('course_id') # Get course ID from query param
        course = Courses.objects(id=course_id).first()
        user = User.objects(email=session['user_email']).first()

        if course and user:
             # Check if already enrolled and active
            existing_enrollment = Enrollment.objects(user_id=str(user.id), course=course, status='active').first()
            if existing_enrollment:
                 flash(f"You are already enrolled in {course.course_name}.", 'info')
                 return redirect(url_for('user_dashboard'))

            # Create new enrollment using ReferenceField
            new_enrollment = Enrollment(
                user_id=str(user.id),
                course=course, # Assign the course object directly
                expire_date=datetime.utcnow() + timedelta(days=90) # Example: 90 days access
            )
            new_enrollment.save()
            flash(f"{course.course_name} enrolled successfully! 😃", 'success')
            return redirect(url_for('user_dashboard'))
        else:
             flash("Course or User not found.", 'danger')
             return redirect(url_for('user_dashboard'))

    # GET Request part
    course_id = request.args.get('course_id')
    if course_id:
        course = Courses.objects(id=course_id).first()
        if course:
             return render_template("Enroll.html", title='Enroll Page', course=course)
        else:
             flash("Course not found.", 'danger')
             return redirect(url_for('user_dashboard'))
    else:
         flash("No course specified for enrollment.", 'warning')
         return redirect(url_for('user_dashboard'))

@app.route("/mentor/course/<course_id>/quiz", methods=["GET"])
@role_required('mentor')
def manage_quiz(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    if not course:
        flash("Course not found or permission denied.", "danger")
        return redirect(url_for('mentor_course_list'))

    # Get or create the quiz for this course
    quiz = Quiz.objects(course=course).first()
    if not quiz:
        # Create a default quiz if none exists
        quiz = Quiz(course=course, title=f"Final Quiz for {course.course_name}")
        quiz.save()
        flash("Quiz created for this course. Add questions below.", "info")

    return render_template("manage_quiz.html", # Create this new template
                           title=f"Manage Quiz - {course.course_name}",
                           course=course,
                           quiz=quiz)

@app.route("/mentor/course/<course_id>/quiz/settings", methods=["POST"])
@role_required('mentor')
def update_quiz_settings(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    if not course:
        flash("Course not found or permission denied.", "danger")
        return redirect(url_for('mentor_course_list'))

    quiz = Quiz.objects(course=course).first()
    if not quiz:
        flash("Quiz not found for this course.", "danger")
        return redirect(url_for('manage_course', course_id=course_id))

    try:
        new_passing_score = int(request.form.get('passing_score_percent'))
        if 0 <= new_passing_score <= 100:
            quiz.passing_score_percent = new_passing_score
            quiz.save()
            flash("Quiz passing score updated.", "success")
        else:
            flash("Passing score must be between 0 and 100.", "danger")
    except (ValueError, TypeError):
        flash("Invalid passing score provided.", "danger")

    return redirect(url_for('manage_quiz', course_id=course_id))


@app.route("/mentor/course/<course_id>/quiz/add_question", methods=["POST"])
@role_required('mentor')
def add_quiz_question(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    quiz = Quiz.objects(course=course).first()

    if not quiz:
        flash("Quiz not found.", "danger")
        return redirect(url_for('manage_course', course_id=course_id))

    try:
        question_text = request.form.get('question_text')
        options = request.form.getlist('options[]') # Get list of options
        correct_option_index = int(request.form.get('correct_option'))

        # Basic Validation
        if not question_text:
            flash("Question text cannot be empty.", "danger")
            return redirect(url_for('manage_quiz', course_id=course_id))
        if len(options) < 2:
             flash("At least two options are required.", "danger")
             return redirect(url_for('manage_quiz', course_id=course_id))
        if not (0 <= correct_option_index < len(options)):
             flash("Invalid correct option selected.", "danger")
             return redirect(url_for('manage_quiz', course_id=course_id))
        if any(not opt for opt in options):
            flash("Option text cannot be empty.", "danger")
            return redirect(url_for('manage_quiz', course_id=course_id))


        new_question = Question(
            text=question_text,
            options=options,
            correct_option=correct_option_index
        )

        # Add the embedded document to the list
        Quiz.objects(id=quiz.id).update_one(push__questions=new_question)

        flash("Question added successfully.", "success")

    except (ValueError, TypeError):
        flash("Invalid data submitted for the question.", "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        print(f"Error adding question: {e}") # Log the error

    return redirect(url_for('manage_quiz', course_id=course_id))

@app.route("/mentor/quiz/<quiz_id>/question/<int:question_index>/delete", methods=["POST"])
@role_required('mentor')
def delete_quiz_question(quiz_id, question_index):
    # Note: Deleting from a ListField by index directly is tricky with update_one.
    # A common pattern is to pull the entire list, modify it in Python, and push it back.
    # Or, pull by matching the specific question details (less reliable if duplicates exist).
    # Let's use the pull-modify-push approach for safety.

    quiz = Quiz.objects(id=quiz_id).first()
    # Security check: Ensure the quiz belongs to the logged-in mentor's course
    if not quiz or quiz.course.mentor_email != session['mentor_email']:
        flash("Quiz not found or permission denied.", "danger")
        return redirect(request.referrer or url_for('mentor_course_list'))

    course_id = quiz.course.id # For redirect

    try:
        if 0 <= question_index < len(quiz.questions):
            question_to_delete = quiz.questions[question_index]
            # Use $pull to remove the specific embedded document instance
            Quiz.objects(id=quiz.id).update_one(pull__questions=question_to_delete)
            flash(f"Question '{question_to_delete.text[:30]}...' deleted.", "success")
        else:
            flash("Invalid question index.", "danger")
    except Exception as e:
        flash(f"Error deleting question: {e}", "danger")
        print(f"Error deleting question: {e}") # Log the error

    return redirect(url_for('manage_quiz', course_id=course_id))

# -------- User Quiz Taking Routes -----------

@app.route("/course/<course_id>/quiz/take", methods=["GET"])
@role_required('user')
def take_quiz(course_id):
    user_email = session['user_email']
    user = User.objects(email=user_email).first() # Fetch user object once
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login')) # Or appropriate redirect

    course = Courses.objects(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for('user_materials'))

    # 1. Check if user is enrolled
    enrollment = Enrollment.objects(user_id=str(user.id), course=course, status='active').first()
    if not enrollment:
         flash("You are not enrolled in this course.", "warning")
         return redirect(url_for('user_materials'))

    # 2. Find the quiz
    quiz = Quiz.objects(course=course).first()
    if not quiz or not quiz.questions:
        flash("No quiz found or quiz has no questions for this course.", "warning")
        return redirect(url_for('user_materials', course_id=course_id))

    # 3. Check lesson completion
    completion_status = CompletionStatus.objects(user_email=user_email, course=course).first()
    units = Unit.objects(course=course)
    total_lessons_count = Lesson.objects(unit__in=units).count()
    completed_lessons_count = len(completion_status.completed_lessons) if completion_status else 0

    if total_lessons_count == 0 or completed_lessons_count < total_lessons_count:
        flash("Please complete all course lessons before taking the final quiz.", "warning")
        return redirect(url_for('user_materials', course_id=course_id))

    # 4. Check if quiz already PASSED (Block only if passed)
    if completion_status and completion_status.quiz_passed:
        flash("You have already passed the quiz for this course.", "info")
        return redirect(url_for('user_materials', course_id=course_id))

    return render_template("take_quiz.html",
                           title=f"Take Quiz - {course.course_name}",
                           course=course,
                           quiz=quiz)

@app.route("/course/<course_id>/quiz/submit", methods=["POST"])
@role_required('user')
def submit_quiz(course_id):
    user_email = session['user_email']
    course = Courses.objects(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for('user_materials'))

    quiz = Quiz.objects(course=course).first()
    if not quiz:
        flash("Quiz not found.", "danger")
        return redirect(url_for('user_materials', course_id=course_id))

    # --- Prerequisite Check ---
    completion_status = CompletionStatus.objects(user_email=user_email, course=course).first()
    units = Unit.objects(course=course)
    total_lessons_count = Lesson.objects(unit__in=units).count()
    completed_lessons_count = len(completion_status.completed_lessons) if completion_status else 0

    if not completion_status or completed_lessons_count < total_lessons_count:
        flash("Cannot submit quiz. Not all lessons completed.", "danger")
        return redirect(url_for('user_materials', course_id=course_id))

    if completion_status.quiz_passed:
        flash("Quiz already passed. Cannot submit again.", "info")
        return redirect(url_for('user_materials', course_id=course_id))

    score = 0
    total_questions = len(quiz.questions)
    user_answers = {}

    for index, question in enumerate(quiz.questions):
        submitted_answer = request.form.get(f'question_{index}')
        if submitted_answer is not None:
            try:
                submitted_answer_index = int(submitted_answer)
                user_answers[index] = submitted_answer_index
                if submitted_answer_index == question.correct_option:
                    score += 1
            except ValueError:
                flash(f"Invalid answer format submitted for question {index + 1}.", "warning")
                pass
        else:
            flash(f"Question {index + 1} was not answered.", "warning")
            user_answers[index] = None

    score_percent = round((score / total_questions) * 100) if total_questions > 0 else 0
    passed = score_percent >= quiz.passing_score_percent

    # Update CompletionStatus (This correctly overwrites previous failed scores)
    completion_status.quiz_taken = True
    completion_status.quiz_score_percent = score_percent
    completion_status.quiz_passed = passed
    completion_status.save()

    if passed:
        flash(f"Congratulations! You passed the quiz with a score of {score_percent}%. You can now generate your certificate.", "success")
    else:
        # Changed message slightly for retake possibility
        flash(f"You did not pass the quiz this time. Your score was {score_percent}%. The required score is {quiz.passing_score_percent}%. Please review the material and try again.", "danger")

    return redirect(url_for('user_materials', course_id=course_id))


@app.route('/generate_certificate')
@role_required('user')
def generate_certificate():
    course_id = request.args.get('course_id')
    user_email = session.get('user_email')
    user = User.objects(email=user_email).first()
    course = None

    if course_id:
        try:
            course = Courses.objects(id=course_id).first()
        except Exception as e:
            print(f"  ERROR fetching course: {e}")
    else:
         print("  ERROR: course_id was None or empty in the request.")

    if not user or not course:
        flash('Course or user not found.', 'error')
        # Redirect to general materials page if course context is lost
        return redirect(url_for('user_materials'))

    # --- Check Completion Status (Lessons AND Quiz) ---
    units = Unit.objects(course=course)
    total_lessons_count = Lesson.objects(unit__in=units).count()
    completion_status = CompletionStatus.objects(user_email=user_email, course=course).first()
    completed_lessons_count = len(completion_status.completed_lessons) if completion_status else 0

    lessons_complete = total_lessons_count > 0 and completed_lessons_count >= total_lessons_count
    quiz_is_passed = completion_status and completion_status.quiz_passed

    # Check if a quiz exists for this course
    quiz_exists = Quiz.objects(course=course).count() > 0

    # Determine if certificate can be generated
    can_generate = False
    if lessons_complete:
        if quiz_exists:
            if quiz_is_passed:
                can_generate = True
            else:
                 flash(f'You must pass the final quiz for {course.course_name} before generating the certificate.', 'warning')
        else:
            # No quiz exists, allow certificate if lessons are done
            can_generate = True
            flash('No final quiz found for this course. Certificate available based on lesson completion.', 'info') # Optional message
    else:
         flash(f'You have not completed all lessons for {course.course_name}. ({completed_lessons_count}/{total_lessons_count})', 'warning')


    if not can_generate:
        return redirect(url_for('user_materials', course_id=course_id))
    # --- End Completion Check ---

    # --- Certificate Generation/Display Logic (Keep as is) ---
    certificates_dir = os.path.join(app.root_path, 'static', 'certificates')
    os.makedirs(certificates_dir, exist_ok=True)
    safe_email = secure_filename(user_email)
    safe_course = secure_filename(course.course_name)
    certificate_filename = f"{safe_email}_{safe_course}_certificate.pdf"
    certificate_path = os.path.join(certificates_dir, certificate_filename)

    existing_cert = Certificate.objects(user_email=user_email, course_name=course.course_name).first()
    if existing_cert:
        certificate_url = url_for('static', filename=f'certificates/{certificate_filename}')
        return render_template("certificate_view.html", certificate_url=certificate_url, course_name=course.course_name)

    try:

        # Import the necessary modules from ReportLab and datetime

        from reportlab.pdfgen import canvas

        from reportlab.lib.pagesizes import letter

        from reportlab.lib.units import inch

        from datetime import datetime



        # Get course name from the query string and user email from the session

        course_name = course.course_name

        if not user or not course:

            flash('Course or user not found.', 'error')

            return redirect(url_for('user_materials'))

        

        # Build the certificates directory path using the full app root

        certificates_dir = os.path.join(app.root_path, 'static', 'certificates')

        os.makedirs(certificates_dir, exist_ok=True)

        

        # Create a safe filename using the user's email and course name

        safe_email = secure_filename(user_email)

        safe_course = secure_filename(course_name)

        certificate_filename = f"{safe_email}_{safe_course}_certificate.pdf"

        

        # Build the full absolute path where the certificate will be saved

        certificate_path = os.path.join(certificates_dir, certificate_filename)

        print("DEBUG: Attempting to save certificate to:", certificate_path)

        

        # If a certificate record already exists, simply return the URL to view it

        existing_cert = Certificate.objects(user_email=user_email, course_name=course_name).first()

        if existing_cert:

            certificate_url = url_for('static', filename=f'certificates/{certificate_filename}')

            return render_template("certificate_view.html", certificate_url=certificate_url, course_name=course_name)

        

        # Generate the PDF certificate using ReportLab

        c = canvas.Canvas(certificate_path, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width / 2, height - 2 * inch, "Certificate of Completion")
        c.setFont("Helvetica", 20)
        c.drawCentredString(width / 2, height - 3 * inch, "This is to certify that")
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width / 2, height - 4 * inch, user.fullname)
        c.setFont("Helvetica", 20)
        c.drawCentredString(width / 2, height - 5 * inch, "has successfully completed the course")
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width / 2, height - 6 * inch, course.course_name) # Use course.course_name
        c.setFont("Helvetica", 16)
        current_date = datetime.now().strftime("%B %d, %Y")
        c.drawCentredString(width / 2, height - 7 * inch, f"Issued on {current_date}")
        # You could add "and passed the final assessment" if quiz_exists
        if quiz_exists:
             c.setFont("Helvetica", 14)
             c.drawCentredString(width / 2, height - 7.5 * inch, "(Including successful completion of the final quiz)")

        c.save()

        # Create Certificate record
        new_cert = Certificate(
            user_email=user_email,
            course_name=course.course_name, # Save course name
            completion_date=datetime.now()
        )
        new_cert.save()
        certificate_url = url_for('static', filename=f'certificates/{certificate_filename}')
        return render_template("certificate_view.html", certificate_url=certificate_url, course_name=course.course_name)

    except Exception as e:
        print(f"DEBUG: Error generating certificate: {e}")
        traceback.print_exc() # Print full traceback
        flash('Error generating certificate', 'error')
        return redirect(url_for('user_materials', course_id=course_id))



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
         mentor_obj = Mentor.objects(email=email).first() # Renamed variable
         if mentor_obj and bcrypt.check_password_hash(mentor_obj.password, password):
             if mentor_obj.status:
                 session.clear() # Clear previous session data
                 session['role'] = 'mentor'
                 session['mentor_logged_in'] = True
                 session['mentor_name'] = mentor_obj.fullname
                 session['mentor_email'] = email
                 # Ensure image_file path is relative to static if stored that way
                 session['profile_picture'] = mentor_obj.image_file # Check if path needs adjustment
                 flash("Login Successful", "success")
                 # *** REDIRECT TO NEW COURSE LIST PAGE ***
                 return redirect(url_for('mentor_course_list'))
             else:
                 flash("Your account is not active. Please contact admin.", "danger")
                 return redirect(url_for('mentor')) # Redirect back to login
         else:
             flash("Login failed! Please check Email and Password.", "danger")
             return redirect(url_for('mentor')) # Redirect back to login
    return render_template("Mentor_Login_Page.html", title="Mentor Login")

@app.route("/Mentor_Course_List", methods=["GET", "POST"])
@role_required('mentor')
def mentor_course_list():
    mentor_email = session['mentor_email']
    courses = Courses.objects(mentor_email=mentor_email).order_by('course_name')

    if request.method == "POST": # Handling Course Creation
        course_name = request.form['coursename']
        course_category = request.form['coursecategory']
        summary = request.form['summary']
        file = request.files.get('imagefile') # Use .get() for safety

        file_path = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            # Save to mentor uploads or general uploads? Decide consistency. Using UPLOAD_FOLDER_1 here.
            file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename)
            try:
                file.save(file_path)
            except Exception as e:
                 flash(f"Error saving course image: {e}", "danger")
                 return redirect(url_for('mentor_course_list'))
        else:
             # Optional: Assign a default image path if none uploaded
             # file_path = 'static/images/default-course.jpg' # Example
             pass

        try:
            new_course = Courses(
                course_name=course_name,
                course_category=course_category,
                mentor_email=mentor_email,
                summary=summary,
                course_image=file_path # Save the path
            )
            new_course.save()
            flash(f'Course "{course_name}" added successfully!', 'success')
        except NotUniqueError:
            flash(f'Course name "{course_name}" already exists. Please choose a different name.', 'danger')
        except ValidationError as e:
             flash(f"Validation Error: {e}", "danger")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

        return redirect(url_for('mentor_course_list')) # Redirect to refresh list

    # GET request: just display the list and add form
    return render_template(
        "Mentor_Course_List.html", # Create this new template
        title="My Courses",
        courses=courses,
        categories=course_categories
    )

# *** NEW: Manage a Specific Course (Units & Lessons) ***
@app.route("/mentor/course/<course_id>/manage", methods=["GET"])
@role_required('mentor')
def manage_course(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    if not course:
        flash("Course not found or you don't have permission.", "danger")
        return redirect(url_for('mentor_course_list'))

    units_with_lessons = []
    units = Unit.objects(course=course).order_by('order', 'title')
    for unit in units:
        lessons = Lesson.objects(unit=unit).order_by('order', 'title')
        units_with_lessons.append({'unit': unit, 'lessons': list(lessons)})

    quiz_exists = Quiz.objects(course=course).count() > 0 # Check if quiz exists

    return render_template("manage_course.html",
                            title=f"Manage {course.course_name}",
                            course=course,
                            units_with_lessons=units_with_lessons,
                            quiz_exists=quiz_exists) # Pass quiz status to template


# *** NEW: Edit Course ***
@app.route("/mentor/course/<course_id>/edit", methods=["GET", "POST"])
@role_required('mentor')
def edit_course(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    if not course:
        flash("Course not found or permission denied.", "danger")
        return redirect(url_for('mentor_course_list'))

    if request.method == "POST":
        try:
            original_name = course.course_name
            course.course_name = request.form['coursename']
            course.course_category = request.form['coursecategory']
            course.summary = request.form['summary']

            file = request.files.get('imagefile')
            if file and file.filename:
                # Optional: Delete old image if replacing
                # if course.course_image and os.path.exists(course.course_image):
                #    os.remove(course.course_image)

                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename)
                file.save(file_path)
                course.course_image = file_path

            course.save()
            flash(f'Course "{course.course_name}" updated successfully!', 'success')
            # If name changed, potentially update related data if needed (e.g., in Feedback, Certificate if not using ID)
            # This depends on whether you store course name or ID in those models.
            # Example: Feedbacks.objects(course_name=original_name).update(set__course_name=course.course_name)

        except NotUniqueError:
             flash(f'Course name "{request.form["coursename"]}" already exists.', 'danger')
             # Reload course object to avoid saving invalid state
             course = Courses.objects(id=course_id).first()
        except ValidationError as e:
             flash(f"Validation Error: {e}", "danger")
             course = Courses.objects(id=course_id).first() # Reload
        except Exception as e:
             flash(f"An error occurred: {e}", "danger")
             course = Courses.objects(id=course_id).first() # Reload
        # No redirect here, stay on edit page to show errors or success
    # GET request shows the form
    return render_template("edit_course.html", # Create this new template
                           title=f"Edit {course.course_name}",
                           course=course,
                           categories=course_categories)

# *** NEW: Delete Course ***
@app.route("/mentor/course/<course_id>/delete", methods=["POST"]) # Use POST for deletion
@role_required('mentor')
def delete_course(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    if course:
        try:
            course_name = course.course_name
            # Cascade delete should handle Units and Lessons due to model definition
            # Optional: Manually delete associated files if needed (cascade doesn't handle external files)
            # units = Unit.objects(course=course)
            # for unit in units:
            #    lessons = Lesson.objects(unit=unit)
            #    for lesson in lessons:
            #       if lesson.upload_file and os.path.exists(lesson.upload_file):
            #          os.remove(lesson.upload_file)
            # Consider deleting enrollments, feedback, certificates related to this course?
            # Enrollment.objects(course=course).delete()
            # Feedbacks.objects(course_name=course_name).delete() # If storing name
            # Certificate.objects(course_name=course_name).delete() # If storing name
            # CompletionStatus.objects(course=course).delete()

            course.delete()
            flash(f'Course "{course_name}" and its content deleted successfully!', 'success')
        except Exception as e:
            flash(f"Error deleting course: {e}", "danger")
    else:
        flash("Course not found or permission denied.", "danger")
    return redirect(url_for('mentor_course_list'))


# *** NEW: Add Unit ***
@app.route("/mentor/course/<course_id>/unit/add", methods=["POST"])
@role_required('mentor')
def add_unit(course_id):
    course = Courses.objects(id=course_id, mentor_email=session['mentor_email']).first()
    if not course:
        flash("Course not found or permission denied.", "danger")
        return redirect(url_for('mentor_course_list'))

    title = request.form.get('unit_title')
    order = request.form.get('unit_order', 0) # Default order to 0

    if not title:
        flash("Unit title is required.", "danger")
    else:
        try:
             new_unit = Unit(
                 title=title,
                 course=course,
                 order=int(order) if order else 0
             )
             new_unit.save()
             flash(f'Unit "{title}" added successfully.', 'success')
        except (ValidationError, ValueError) as e:
             flash(f"Error adding unit: {e}", "danger")
        except Exception as e:
             flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for('manage_course', course_id=course_id))

# *** NEW: Edit Unit ***
@app.route("/mentor/unit/<unit_id>/edit", methods=["POST"])
@role_required('mentor')
def edit_unit(unit_id):
    unit = Unit.objects(id=unit_id).first()
    # Check if mentor owns the course associated with the unit
    if not unit or unit.course.mentor_email != session['mentor_email']:
        flash("Unit not found or permission denied.", "danger")
        return redirect(request.referrer or url_for('mentor_course_list')) # Redirect back or to list

    new_title = request.form.get('unit_title')
    new_order = request.form.get('unit_order', unit.order)

    if not new_title:
         flash("Unit title cannot be empty.", "danger")
    else:
         try:
             unit.title = new_title
             unit.order = int(new_order)
             unit.save()
             flash(f'Unit "{unit.title}" updated.', 'success')
         except (ValidationError, ValueError) as e:
              flash(f"Error updating unit: {e}", "danger")
         except Exception as e:
              flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for('manage_course', course_id=unit.course.id))


# *** NEW: Delete Unit ***
@app.route("/mentor/unit/<unit_id>/delete", methods=["POST"])
@role_required('mentor')
def delete_unit(unit_id):
    unit = Unit.objects(id=unit_id).first()
    if unit and unit.course.mentor_email == session['mentor_email']:
        course_id = unit.course.id
        try:
             unit_title = unit.title
             unit.delete()
             flash(f'Unit "{unit_title}" and its lessons deleted.', 'success')
        except Exception as e:
             flash(f"Error deleting unit: {e}", "danger")
        return redirect(url_for('manage_course', course_id=course_id))
    else:
        flash("Unit not found or permission denied.", "danger")
        return redirect(request.referrer or url_for('mentor_course_list'))


# *** NEW: Add Lesson ***
@app.route("/mentor/unit/<unit_id>/lesson/add", methods=["POST"])
@role_required('mentor')
def add_lesson(unit_id):
    unit = Unit.objects(id=unit_id).first()
    # Check ownership
    if not unit or unit.course.mentor_email != session['mentor_email']:
        flash("Unit not found or permission denied.", "danger")
        return redirect(request.referrer or url_for('mentor_course_list'))

    title = request.form.get('lesson_title')
    description = request.form.get('lesson_description')
    file_type = request.form.get('lesson_file_type')
    order = request.form.get('lesson_order', 0)
    external_url = request.form.get('lesson_external_url') # Get URL if provided
    file = request.files.get('lesson_file')

    if not title or not file_type:
        flash("Lesson title and file type are required.", "danger")
        return redirect(url_for('manage_course', course_id=unit.course.id))

    file_path = None
    # Handle file upload only if a file is provided and type requires it (e.g., Video, Material)
    if file and file.filename and file_type in ['Video', 'Material']:
        filename = secure_filename(file.filename)
        # Consider organizing uploads by course/unit?
        # file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], str(unit.course.id), str(unit.id), filename)
        # os.makedirs(os.path.dirname(file_path), exist_ok=True) # Create dirs if needed
        file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename) # Simpler path for now
        try:
            file.save(file_path)
        except Exception as e:
            flash(f"Error saving lesson file: {e}", "danger")
            return redirect(url_for('manage_course', course_id=unit.course.id))
    elif file_type in ['Video', 'Material'] and not external_url:
        # If type requires file but none provided and no external URL, maybe flash warning?
        # flash("Please provide a file or an external URL for this lesson type.", "warning")
        pass # Allow creation without file for now, maybe add URL later

    try:
        new_lesson = Lesson(
            title=title,
            unit=unit,
            file_type=file_type,
            description=description,
            upload_file=file_path, # Will be None if no file uploaded/saved
            external_url=external_url if external_url else None,
            order=int(order) if order else 0
        )
        new_lesson.save()
        flash(f'Lesson "{title}" added to unit "{unit.title}".', 'success')
    except (ValidationError, ValueError) as e:
        flash(f"Error adding lesson: {e}", "danger")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for('manage_course', course_id=unit.course.id))

# *** NEW: Edit Lesson ***
@app.route("/mentor/lesson/<lesson_id>/edit", methods=["POST"])
@role_required('mentor')
def edit_lesson(lesson_id):
    lesson = Lesson.objects(id=lesson_id).first()
    # Check ownership via unit and course
    if not lesson or lesson.unit.course.mentor_email != session['mentor_email']:
        flash("Lesson not found or permission denied.", "danger")
        return redirect(request.referrer or url_for('mentor_course_list'))

    course_id = lesson.unit.course.id # Get course_id for redirect

    new_title = request.form.get('lesson_title')
    new_description = request.form.get('lesson_description')
    new_file_type = request.form.get('lesson_file_type')
    new_order = request.form.get('lesson_order', lesson.order)
    new_external_url = request.form.get('lesson_external_url')
    new_file = request.files.get('lesson_file')

    if not new_title or not new_file_type:
         flash("Lesson title and file type are required.", "danger")
    else:
        try:
             lesson.title = new_title
             lesson.description = new_description
             lesson.file_type = new_file_type
             lesson.order = int(new_order) if new_order else lesson.order
             lesson.external_url = new_external_url if new_external_url else None

             if new_file and new_file.filename:
                 # Optional: Delete old file if it exists and is being replaced
                 # if lesson.upload_file and os.path.exists(lesson.upload_file):
                 #    os.remove(lesson.upload_file)

                 filename = secure_filename(new_file.filename)
                 file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename)
                 new_file.save(file_path)
                 lesson.upload_file = file_path
             elif request.form.get('remove_current_file'): # Add a checkbox in the form if needed
                  # Optional: Remove existing file without uploading new one
                 # if lesson.upload_file and os.path.exists(lesson.upload_file):
                 #    os.remove(lesson.upload_file)
                 lesson.upload_file = None


             lesson.save()
             flash(f'Lesson "{lesson.title}" updated.', 'success')
        except (ValidationError, ValueError) as e:
             flash(f"Error updating lesson: {e}", "danger")
        except Exception as e:
             flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for('manage_course', course_id=course_id))


# *** NEW: Delete Lesson ***
@app.route("/mentor/lesson/<lesson_id>/delete", methods=["POST"])
@role_required('mentor')
def delete_lesson(lesson_id):
    lesson = Lesson.objects(id=lesson_id).first()
    if lesson and lesson.unit.course.mentor_email == session['mentor_email']:
        course_id = lesson.unit.course.id
        try:
            lesson_title = lesson.title
            # Optional: Delete associated file
            if lesson.upload_file and os.path.exists(lesson.upload_file):
                 try:
                      os.remove(lesson.upload_file)
                 except OSError as e:
                      print(f"Error deleting file {lesson.upload_file}: {e}")
                      flash(f"Lesson DB entry deleted, but could not delete file: {e}", "warning")

            # Also remove from CompletionStatus if needed
            CompletionStatus.objects().update(pull__completed_lessons=lesson)

            lesson.delete()
            flash(f'Lesson "{lesson_title}" deleted.', 'success')
        except Exception as e:
            flash(f"Error deleting lesson: {e}", "danger")

        return redirect(url_for('manage_course', course_id=course_id))
    else:
        flash("Lesson not found or permission denied.", "danger")
        return redirect(request.referrer or url_for('mentor_course_list'))



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

# *** MODIFIED: Mentor Dashboard - Simplified, perhaps shows stats or links ***
@app.route("/Mentor_Dashboard")
@role_required('mentor')
def mentor_dashboard():
    # This dashboard could show overview stats or just redirect to the course list
    mentor_email = session['mentor_email']
    course_count = Courses.objects(mentor_email=mentor_email).count()
    # Could add counts for units, lessons, enrolled students etc.
    # enrolled_users_count = len(get_enrolled_details()) # Fetch count if needed

    return render_template("Mentor_Dashboard_Simple.html", # Consider a simpler dashboard template
                           title="Mentor Dashboard",
                           course_count=course_count)
                           # enrolled_users_count=enrolled_users_count)
            
@app.route("/Enrolled_Users")
@role_required('mentor')
def enrolled_users():
    # Use the updated get_enrolled_details which returns filtered list
    enrolled_users_list = get_enrolled_details()
    return render_template('Enrolled_Users.html', title="Enrolled Users", enrolled_users=enrolled_users_list)

@app.route("/View_Feedback")
@role_required('mentor')
def view_feedback():
     # Filter feedback for courses owned by this mentor
    mentor_email = session['mentor_email']
    mentor_courses = Courses.objects(mentor_email=mentor_email)
    mentor_course_names = [course.course_name for course in mentor_courses]

    grouped_feedbacks = {}
    # Fetch feedback only for the mentor's courses
    mentor_feedbacks = Feedbacks.objects(course_name__in=mentor_course_names)

    # Group by category (of the course the feedback is for)
    for feedback_item in mentor_feedbacks:
         category = feedback_item.course_category # Assumes feedback saves category
         if category not in grouped_feedbacks:
             grouped_feedbacks[category] = []
         grouped_feedbacks[category].append(feedback_item)

    # Get categories relevant to this mentor's courses
    relevant_categories = sorted(list(set(course.course_category for course in mentor_courses if course.course_category)))

    return render_template('View_Feedback.html',
                            grouped_feedbacks=grouped_feedbacks,
                            categories=relevant_categories # Show only relevant categories
                            )

@app.route('/mentor/edit_profile', methods=['GET', 'POST'])
@role_required('mentor')
def mentor_edit_profile():
    if not session.get('mentor_logged_in'):
        return redirect(url_for('mentor'))

    mentor = Mentor.objects(email=session['mentor_email']).first()

    if not mentor:
        flash("Mentor not found", "danger")
        return redirect(url_for('mentor_dashboard'))

    if request.method == 'POST':
        mentor.fullname = request.form['fullname']
        mentor.phonenumber = request.form['phonenumber']
        mentor.qualification = request.form['qualification']
        mentor.experience = request.form['experience']
        mentor.linkedin = request.form['linkedin']

        # ✅ Handle profile picture update
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                mentor.image_file = file_path
                session['profile_picture'] = file_path  # Also update in session

        mentor.save()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('mentor_dashboard'))

    return render_template("mentor_edit_profile.html", mentor=mentor)




@app.route("/Mentor_Logout")
def mentor_logout():
    session.pop('mentor_logged_in', None)  # Removes the session variable
    session.pop('mentor_email', None)  # Optionally removes mentor email
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route("/api/chatbot", methods=["POST"])
@role_required('user') # Ensure only logged-in users can access
@csrf.exempt # Exempt CSRF for API endpoint if frontend makes non-form POSTs
def chat_api():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_query = data.get("message")

    if not user_query:
        return jsonify({"error": "Missing 'message' in request"}), 400

    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "User session not found"}), 401


    try:
        chatbot = get_chatbot_instance()


        response = chatbot.get_response(user_email, user_query)

        return jsonify({"response": response})

    except Exception as e:
        print(f"Error in chat API endpoint: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error processing chat message."}), 500


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
    os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
    app.run(port=5000, debug=True)