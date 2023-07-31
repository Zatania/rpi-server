from flask import Flask, render_template, url_for, request, redirect, flash, after_this_request
import flask_excel as excel
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from time import sleep
import drivers
import serial
import adafruit_fingerprint
import threading
app = Flask(__name__)
excel.init_excel(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SECRET_KEY'] = 'g1mo9je(e9jo0uv+(8(^1fl31dd%$5rldf04zm$^20am)z=c(h'
db = SQLAlchemy(app)

##### DATETIME NOW #####
now = datetime.now()

##### FINGERPRINT ######
uart = serial.Serial("/dev/ttyAMA0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

##### LCD #####
display = drivers.Lcd()

##### GSM #####
sms = None

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fullname = db.Column(db.String(1000), nullable=False)
    date_added = db.Column(db.DateTime, default=now)

    def __repr__(self):
        return '<User %r>' % self.id

class Courses(db.Model, UserMixin):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)

    course_name = db.Column(db.String(255), nullable=False)
    course_code = db.Column(db.String(255), nullable=False)
    course_description = db.Column(db.String(1000), nullable=False)
    course_units = db.Column(db.String(255), nullable=False)
    course_teacher = db.Column(db.ForeignKey('user.fullname'), nullable=False)
    date_added = db.Column(db.DateTime, default=now)

    teacher = db.relationship('User', foreign_keys=course_teacher)
    def __repr__(self):
        return '<Courses %r>' % self.id
    
class Students(db.Model, UserMixin):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)

    fingerprint_id = db.Column(db.Integer, nullable=False)
    fullname = db.Column(db.String(1000), nullable=False)
    course = db.Column(db.String(255), nullable=False)
    studentid = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(255), nullable=False)
    program = db.Column(db.String(255), nullable=False)
    year = db.Column(db.String(255), nullable=False)
    parentphone = db.Column(db.String(255), nullable=False)
    teacher_name = db.Column(db.String(1000), db.ForeignKey('user.fullname'), nullable=False)
    date_added = db.Column(db.DateTime, default=now)

    teacher = db.relationship('User', foreign_keys=teacher_name)

    def __repr__(self):
        return '<Students %r>' % self.id

class History(db.Model, UserMixin):
    __tablename__ = 'history'
    id = db.Column(db.Integer, primary_key=True)

    studentid = db.Column(db.String(255), nullable=False)
    student_name = db.Column(db.String(1000), nullable=False)
    program = db.Column(db.String(255), nullable=False)
    year = db.Column(db.String(255), nullable=False)
    course = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(255), default='Absent')
    date_timein = db.Column(db.DateTime, default=now)
    
    def __repr__(self):
        return '<History %r>' % self.id
    
@app.cli.command('createdb')
def db_create():
    db.create_all()
    print('Database created!')
@app.cli.command('dropdb')
def db_drop():
    db.drop_all()
    print('Database dropped!')
@app.cli.command('create-admin')
def db_seed():
    hashed_password = generate_password_hash('admin')
    user1 = User(username='admin', password=hashed_password, fullname='Admin')
    db.session.add(user1)
    db.session.commit()
    print('Database seeded!')

login_manager = LoginManager()
login_manager.login_view = 'index.html'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('index'))

################ LOGIN/LOGOUT ################
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.username == 'admin':
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('dashboard'))
    display.lcd_display_string("Student Attendance", 1)
    display.lcd_display_string("System", 2)
    display.lcd_display_string("Please login", 4)
    return render_template("login.html")

@app.route('/', methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username.lower()).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            if user.username == 'admin':
                display.lcd_clear()
                display.lcd_display_string("Logging in...", 1)
                sleep(2)
                display.lcd_clear()
                return redirect(url_for('admin'))
            else:
                display.lcd_clear()
                display.lcd_display_string("Logging in...", 1)
                sleep(2)
                display.lcd_clear()
                return redirect(url_for('dashboard'))
        else:
            flash('Please check your login details and try again.')

    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    display.lcd_clear()
    display.lcd_display_string("Logging out...", 1)
    sleep(2)
    display.lcd_clear()
    return redirect(url_for('index'))

################ TEACHER DASHBOARD ################
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Welcome Teacher", 3)
        display.lcd_display_string(f"{current_user.fullname}", 4)
        return render_template("dashboard.html", fullname=current_user.fullname, id=current_user.id)

################ HISTORY ################
@app.route('/history/<id>')
@login_required
def history(id):
    teacher = User.query.get_or_404(id)
    students = Students.query.filter_by(teacher_name=teacher.fullname).all()
    student_histories = {}
    histories = []  # Initialize the histories list before the loop

    for student in students:
        # Fetch student histories and extend the list
        student_histories = History.query.filter_by(studentid=student.studentid).all()
        histories.extend(student_histories)

    if current_user.username == 'admin':
        return redirect(url_for('admin'))
    else:
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Attendance History", 4)
        return render_template("history.html", histories=histories, id=teacher.id)


##### EXCEL EXPORT #####
@app.route('/download/<id>', methods=["GET"])
@login_required
def download(id):
    teacher = User.query.get_or_404(id)
    students = Students.query.filter_by(teacher_name=teacher.fullname).all()
    student_histories = {}
    histories = []  # Initialize the histories list before the loop

    for student in students:
        # Fetch student histories and extend the list
        student_histories = History.query.filter_by(studentid=student.studentid).all()
        histories.extend(student_histories)

    if current_user.username == 'admin':
        return redirect(url_for('admin'))
    else:
        display.lcd_clear()
        display.lcd_display_string("Downloading History...", 1)
        sleep(2)
        column_names = ['id','studentid', 'student_name', 'program', 'year', 'course', 'status', 'date_timein']
        response = excel.make_response_from_query_sets(histories, column_names, "xlsx", file_name="Student Attendance")
        display.lcd_clear()
        display.lcd_display_string("History Downloaded", 1)
        sleep(2)
        
        return response
@app.route('/attendance')
@login_required
def attendance():
    if current_user.username == 'admin':
        return redirect(url_for('admin'))
    else:
        return render_template("attendance.html")

@app.route('/attendance/scan')
@login_required
def attendance_scan():
    if current_user.username == 'admin':
        return redirect(url_for('admin'))
    else:
        if get_fingerprint():
            students = Students.query.filter_by(id=finger.finger_id).first()
            number = students.parentphone
            name = students.fullname
            course = students.course
            attendance = History(studentid=students.studentid, student_name=students.fullname, program=students.program, year=students.year, course=course, status='Present')

            db.session.add(attendance)
            db.session.commit()

            if open_serial_port():
                try:
                    response = send_at_command('AT\r')
                    print("AT Command response:", response)

                    response = send_at_command('AT+CMGF=1\r')
                    print("CMGF response:", response)

                    response = send_at_command(f'AT+CMGS="{number}"\r')
                    print("CMGS response:", response)

                    response = send_at_command(f'Your child {name} has entered their {course} class. \x1A')
                    print("Sending SMS response:", response)

                except Exception as e:
                    print("Error:", str(e))

                finally:
                    sms.close()
                    print("Serial port is closed.")
                    display.lcd_display_string("SMS Sent", 1)
                    sleep(1)
            else:
                print("Cannot proceed as the serial port is not open.")

            display.lcd_clear()
            return redirect(url_for('attendance'))
        else:
            display.lcd_clear()
            return redirect(url_for('attendance'))
def open_serial_port():
    global sms
    try:
        sms = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)
        if sms.is_open:
            print("Serial port is open.")
            return True
        else:
            print("Serial port could not be opened.")
            return False
    except Exception as e:
        print("Error:", str(e))
        return False

def send_at_command(command):
    sms.write(command.encode())
    sleep(0.5)
    response = sms.readlines()
    return b"".join(response).decode()

def get_fingerprint():
    display.lcd_display_string("Place finger", 1)
    while finger.get_image() != adafruit_fingerprint.OK:
        pass
    display.lcd_clear()
    display.lcd_display_string("Templating", 1)
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        display.lcd_clear()
        display.lcd_display_string("Not found.", 1)
        sleep(1)
        return False
    display.lcd_display_string("Searching", 1)
    if finger.finger_search() != adafruit_fingerprint.OK:
        display.lcd_clear()
        display.lcd_display_string("Not found.", 1)
        sleep(1)
        return False

    display.lcd_clear()
    display.lcd_display_string("Success", 1)
    return True
################ STUDENTS ################
@app.route('/students/list')
@login_required
def students_list():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Students List", 4)
        students = Students.query.filter_by(teacher_name=current_user.fullname).order_by(Students.date_added).all()

        return render_template("students-db.html", students=students)

@app.route('/students/add', methods=["POST", "GET"])
@login_required
def students_add():
    MAX_FINGERPRINT_ID = 162
    courses = Courses.query.filter_by(course_teacher=current_user.fullname)

    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            fullname = request.form.get('fullname')
            course = request.form.get('coursename')
            studentid = request.form.get('studentid')
            department = request.form.get('department')
            program = request.form.get('program')
            year = request.form.get('year')
            parentphone = request.form.get('parentphone')

            #Checking
            student_check = Students.query.filter_by(studentid=studentid).first()
            
            if student_check:
                flash('Student Exists. Try again.')
                display.lcd_clear()
                display.lcd_display_string("Student Exists", 1)
                display.lcd_display_string("Try again.", 2)
                sleep(2)
                return redirect(url_for('students_add'))

            # Check if the fingerprint_id is available
            available_fingerprint = None
            existing_students = Students.query.all()
            all_fingerprint_ids = set(student.fingerprint_id for student in existing_students)

            for i in range(1, MAX_FINGERPRINT_ID + 1):
                if i not in all_fingerprint_ids:
                    available_fingerprint = i
                    break

            if available_fingerprint is None:
                return "No available fingerprint_id, cannot add a new student."

            # Commit Data into Database
            new_student = Students(fullname=fullname, course=course, studentid=studentid, department=department, program=program, year=year, teacher_name=current_user.fullname, parentphone=parentphone, fingerprint_id=available_fingerprint)

            db.session.add(new_student)
            db.session.commit()

            # Query into Students and get ID
            query = Students.query.filter_by(fullname=fullname).first()

            location = query.fingerprint_id
            
            # Wait for a finger to be read
            enroll(location)
            sleep(2)
            display.lcd_clear()

            return redirect(url_for('students_list'))
            
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Students Add", 4)
        return render_template("students-add.html", courses=courses)

#Fingerprint Enroll
def enroll(location):
    for fingerimg in range(1, 3):
        if fingerimg == 1:
            display.lcd_clear()
            display.lcd_display_string("Place finger", 1)
        else:
            display.lcd_clear()
            display.lcd_display_string("Place again", 1)

        while True:
            i = finger.get_image()
            if i == adafruit_fingerprint.OK:
                display.lcd_clear()
                display.lcd_display_string("Image taken", 1)
                break
            if i == adafruit_fingerprint.NOFINGER:
                display.lcd_clear()
                display.lcd_display_string("Place finger", 1)
            elif i == adafruit_fingerprint.IMAGEFAIL:
                display.lcd_clear()
                display.lcd_display_string("Imaging error", 1)
            else:
                display.lcd_clear()
                display.lcd_display_string("Other error", 1)
            # Add a delay here to allow the user to see the error message
            sleep(2)
            display.lcd_clear()

        display.lcd_display_string("Templating...", 1)
        while True:
            i = finger.image_2_tz(fingerimg)
            if i == adafruit_fingerprint.OK:
                display.lcd_clear()
                display.lcd_display_string("Templated", 1)
                break
            else:
                if i == adafruit_fingerprint.IMAGEMESS:
                    display.lcd_clear()
                    display.lcd_display_string("Image too messy", 1)
                elif i == adafruit_fingerprint.FEATUREFAIL:
                    display.lcd_clear()
                    display.lcd_display_string("Could not identify features", 1)
                elif i == adafruit_fingerprint.INVALIDIMAGE:
                    display.lcd_clear()
                    display.lcd_display_string("Image invalid", 1)
                else:
                    display.lcd_clear()
                    display.lcd_display_string("Other error", 1)
                # Add a delay here to allow the user to see the error message
                sleep(2)
                display.lcd_clear()

        if fingerimg == 1:
            display.lcd_clear()
            display.lcd_display_string("Remove finger", 1)
            sleep(1)
            while i != adafruit_fingerprint.NOFINGER:
                i = finger.get_image()
    
    display.lcd_clear()
    display.lcd_display_string("Creating model...", 1)
    while True:
        i = finger.create_model()
        if i == adafruit_fingerprint.OK:
            display.lcd_clear()
            display.lcd_display_string("Fingerprint", 1)
            display.lcd_display_string("Created", 2)
            break
        else:
            if i == adafruit_fingerprint.ENROLLMISMATCH:
                display.lcd_clear()
                display.lcd_display_string("Prints did not match", 1)
            else:
                display.lcd_clear()
                display.lcd_display_string("Other error", 1)
            # Add a delay here to allow the user to see the error message
            sleep(2)
            display.lcd_clear()

    display.lcd_display_string("Adding Student", 1)
    i = finger.store_model(location)
    if i == adafruit_fingerprint.OK:
        display.lcd_clear()
        display.lcd_display_string("Student Added", 1)
    else:
        if i == adafruit_fingerprint.BADLOCATION:
            display.lcd_clear()
            display.lcd_display_string("Bad storage location", 1)
        elif i == adafruit_fingerprint.FLASHERR:
            display.lcd_clear()
            display.lcd_display_string("Flash storage error", 1)
        else:
            display.lcd_clear()
            display.lcd_display_string("Other error", 1)
        # Add a delay here to allow the user to see the error message
        sleep(2)
        display.lcd_clear()

    return True

@app.route('/students/update/<id>', methods=["POST", "GET"])
@login_required
def students_update(id):
    courses = Courses.query.all()
    student = Students.query.get_or_404(id)

    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            student.fullname = request.form.get('fullname')
            student.course = request.form.get('coursename')
            student.studentid = request.form.get('studentid')
            student.department = request.form.get('department')
            student.program = request.form.get('program')
            student.year = request.form.get('year')
            student.parentphone = request.form.get('parentphone')

            db.session.commit()

            return redirect(url_for('students_list'))
            
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Students Update", 4)
        return render_template("students-update.html", courses=courses, student=student)

@app.route('/students/delete/<id>')
@login_required
def students_delete(id):
    #Questionable whether to delete history of deleted student or not
    student = Students.query.get_or_404(id)
    history = History.query.get_or_404(student.id)

    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        display.lcd_clear()
        display.lcd_display_string("Deleting Student", 1)
        display.lcd_display_string(f"{ student.fullname }", 2)
        sleep(2)

        if finger.delete_model(student.fingerprint_id) == adafruit_fingerprint.OK:
            display.lcd_clear()
            display.lcd_display_string("Student Fingerprint", 1)
            display.lcd_display_string("Deleted...", 2)
            sleep(2)

        db.session.delete(history)
        db.session.delete(student)

        display.lcd_clear()
        display.lcd_display_string("Student Deleted...", 1)
        sleep(2)

        db.session.commit()

        return redirect(url_for('students_list'))

    return redirect(url_for('index'))
@app.route('/clear-fingerprint')
@login_required
def clear_fingerprint():
    if finger.empty_library() == adafruit_fingerprint.OK:
        display.lcd_clear()
        display.lcd_display_string("Library empty!", 1)
        sleep(2)
        display.lcd_clear()
        return redirect(url_for('students_list'))
    else:
        display.lcd_clear()
        print("Failed to empty library")
        sleep(2)
        display.lcd_clear()
################ COURSES ################    
@app.route('/courses/list')
@login_required
def courses():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        courses = Courses.query.filter_by(course_teacher=current_user.fullname).order_by(Courses.date_added).all()

        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Courses List", 4)

        return render_template("courses-db.html", courses=courses)
    
@app.route('/courses/add', methods=["POST", "GET"])
@login_required
def courses_add():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            course_name = request.form.get('course_name')
            course_code = request.form.get('course_code')
            course_description = request.form.get('course_description')
            course_units = request.form.get('course_units')
            
            #Checking
            course_check = Courses.query.filter_by(course_code=course_code).first()
            
            if course_check:
                flash('Course Exists. Try again.')
                display.lcd_clear()
                display.lcd_display_string("Course Exists", 1)
                display.lcd_display_string("Try again.", 2)
                sleep(2)
                return redirect(url_for('courses_add'))
            new_course = Courses(course_name=course_name, course_code=course_code, course_description=course_description, course_units=course_units, course_teacher=current_user.fullname)

            display.lcd_clear()
            display.lcd_display_string("Adding course...", 1)
            sleep(2)

            db.session.add(new_course)
            db.session.commit()

            display.lcd_clear()
            display.lcd_display_string("Course Added", 1)
            sleep(2)

            return redirect(url_for('courses'))

        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Add Course", 4)
        return render_template("courses-add.html")
    
################ ADMIN DASHBOARD ################
@app.route('/admin')
@login_required
def admin():
    if current_user.username == 'admin':
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Welcome Admin", 4)

        return render_template("admin.html", fullname=current_user.fullname)
    else:
        return redirect(url_for('index'))

################ TEACHERS ################
@app.route('/teachers')
@login_required
def teachers():
    if current_user.username == 'admin':
        teachers = User.query.all()

        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Teachers List", 4)

        return render_template("teachers.html", teachers=teachers)
    return redirect(url_for('index'))

@app.route('/teachers/add', methods=["POST", "GET"])
@login_required
def addteacher():
    if current_user.username == 'admin':
        if request.method == "POST": 
            fullname = request.form.get('fullname')
            username = request.form.get('username')
            password = request.form.get('password')

            user = User.query.filter_by(username=username).first()
            
            if user:
                flash('Username Exists. Try another one.')
                display.lcd_clear()
                display.lcd_display_string("Username Exists", 1)
                display.lcd_display_string("Try another one.", 2)
                sleep(2)
                return redirect(url_for('addteacher'))
            
            new_user = User(fullname=fullname, username=username.lower(), password=generate_password_hash(password))

            
            display.lcd_clear()
            display.lcd_display_string("Adding Teacher...", 1)
            sleep(2)

            db.session.add(new_user)
            db.session.commit()
            
            display.lcd_clear()
            display.lcd_display_string("Teacher Added", 1)
            sleep(2)
            
            return redirect(url_for('teachers'))
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Add Teacher", 4)
        return render_template("addteacher.html")
    return redirect(url_for('index'))


@app.route('/teachers/update/<id>', methods=["POST", "GET"])
@login_required
def updateteacher(id):
    if current_user.username == 'admin':
        teacher = User.query.get_or_404(id)

        if request.method == "POST":
            teacher.fullname = request.form['fullname']
            teacher.username = request.form['username']
            teacher.password = generate_password_hash(request.form['password'])

            display.lcd_clear()
            display.lcd_display_string("Updating Teacher", 1)
            sleep(2)

            db.session.commit()

            display.lcd_clear()
            display.lcd_display_string("Teacher Updated", 1)
            sleep(2)

            return redirect(url_for('teachers'))
        else:
            display.lcd_clear()
            display.lcd_display_string("Student Attendance", 1)
            display.lcd_display_string("System", 2)
            display.lcd_display_string("Update Teacher", 4)

            return render_template("updateteacher.html", teacher=teacher)
    return redirect(url_for('index'))

@app.route('/teachers/delete/<id>')
@login_required
def deleteteacher(id):
    if current_user.username == 'admin':
        teacher = User.query.get_or_404(id)
        student = Students.query.get_or_404(id)
        history = History.query.get_or_404(student.id)
        
        display.lcd_clear()
        display.lcd_display_string("Deleting Teacher", 1)
        display.lcd_display_string(f"{{ teacher.fullname }}", 2)

        db.session.delete(teacher)

        display.lcd_clear()
        display.lcd_display_string("Teacher Deleted...", 1)

        db.session.commit()

        return redirect(url_for('teachers'))
    return redirect(url_for('index'))

@app.route('/students')
@login_required
def students():
    if current_user.username == 'admin':
        students = Students.query.order_by(Students.date_added).all()

        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Students List", 4)

        return render_template("students.html", students=students)
    return redirect(url_for('index'))

#404 ERROR HANDLING
@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for('index'))