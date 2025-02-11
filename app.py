from flask import Flask, render_template, redirect, url_for, flash, request, session
import secrets, os, sys
from werkzeug.utils import secure_filename
from models import db, User, Queries, Materials
from forms import LoginForm
import subprocess, logging as log

try:
    from flask_bcrypt import Bcrypt
except ImportError:
    print("some_library is not installed. Installing now...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask-Bcrypt'])
    from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

app.config["SECRET_KEY"] = secrets.token_hex(21)
app.config["MONGODB_SETTINGS"] = {
                                'db': 'Mentoroiddb', 
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

COURSES = [
    {'name': 'Course 1', 'link': '#'},
    {'name': 'Course 2', 'link': '#'},
    {'name': 'Course 3', 'link': '#'}
]

@app.route("/")
@app.route("/Home")
def home():
    return render_template("Home_Page.html", title="Home Page")

@app.route("/About")
def about():
    return render_template("About_Page.html", title="About Page")

# @app.route("/Contact", methods=["GET", "POST"])
# def contact():
#     if request.method == "POST":
#         fullname = request.form["fullname"]
#         email = request.form["email"]
#         phonenumber = request.form['phone']
#         subject = request.form['subject']
#         message = request.form['yourmessage']

#         new_query = Queries(
#             fullname=fullname,
#             email=email,
#             phonenumber=phonenumber,
#             subject=subject,
#             message=message
#         )
#         new_query.save()  # Save the query to MongoDB

#         flash('Query received successfully! You will receive an email for further information.')
#         return redirect(url_for('contact'))

#     return render_template("Contact_Page.html", title="Contact Page")

@app.route("/Register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form['fullname']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        age = request.form['age']
        phonenumber = request.form['phonenumber']
        email = request.form['email']
        address = request.form['address']

        if 'imagefile' not in request.files:
            flash('No file part')
            return redirect(url_for('register'))

        existing_user = User.objects(email=email).first()  # Query for existing user
        if existing_user:
            flash('Email already exists. Please choose a different email.', 'info')
            return redirect(url_for('register'))

        file = request.files['imagefile']
        if file.filename == '':
            filename = "default.jpg"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

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

    return render_template("Register_Page.html", title="Register Page")

# ---------- user routes ----------

@app.route("/User_Login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.objects(email=form.email.data).first()  # Query for user
        if user and bcrypt.check_password_hash(user.password, form.password.data):
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
def user_dashboard():
    session.pop('search_materials', None)
    return render_template("User_Dashboard.html", title = "User Dashboard", courses=COURSES)

@app.route("/User_Profile")
def profile():
    return render_template("User_Profile.html", title = "User Profile", courses=COURSES)

@app.route("/User_Materials")
def user_materials():
    return render_template("User_Materials.html", title = "User Materials", courses=COURSES)
    
@app.route('/search')
def search():
    to_be_searched = request.args.get('query')
    session['search_materials'] = to_be_searched
    flash(to_be_searched)
    return redirect("/User_Materials")
    # we can use the 'query' variable to filter our materials
    # For example, you might want to search in a database or a list of materials
    # return render_template('search_results.html', query=query)

@app.route("/Logout")
def logout():
    session.pop('user_logged_in', None)  # Removes the session variable
    session.pop('user_email', None)  # Optionally removes user email
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route("/Mentor_Login", methods=["GET", "POST"])
def mentor():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if username == "Mentor" and password == "Mentor":
            session['mentor_logged_in'] = True  # Sets session variable
            session['mentor_email'] = username
            flash("Login Successful", "success")
            return redirect("/Mentor_Dashboard")
        else:
            flash("Login failed! Please check the Username and Password.", "danger")
            return redirect("/Mentor_Login")
    return render_template("Mentor_Login_Page.html", title = "Mentor Login")

@app.route("/Mentor_Dashboard")
def mentor_dashboard():
    return render_template("Mentor_Dashboard.html", title = "Mentor Dashboard", courses=COURSES)

@app.route("/Content_Upload", methods = ["GET", "POST"])
def content_upload():
    course = request.args.get('course')
    if request.method == "POST":
        title = request.form['title']
        description = request.form['description']
        
        if 'file' not in request.files:
            flash('No file part')
            return render_template("Content_Upload.html", title = "Content Upload", courses=COURSES, course=course)

        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return render_template("Content_Upload.html", title = "Content Upload", courses=COURSES, course=course)

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER_1'], filename)
            file.save(file_path)

            new_material = Materials(
                course_name=course,
                title=title,
                description=description,
                upload_file=file_path
            )
            new_material.save()  # Save the user to MongoDB
            flash('Upload successful!', 'success')
            
            return render_template("Content_Upload.html", title = "Content Upload", courses=COURSES, course=course)

    return render_template("Content_Upload.html", title = "Content Upload", courses=COURSES, course=course)

@app.route("/Mentor_Logout")
def mentor_logout():
    session.pop('mentor_logged_in', None)  # Removes the session variable
    session.pop('mentor_email', None)  # Optionally removes mentor email
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(port=5000, debug=True)