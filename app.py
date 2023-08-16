from flask import Flask, render_template, url_for, request, redirect, flash, after_this_request
import flask_excel as excel
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from time import sleep
import random
import string
import drivers
import serial
import adafruit_fingerprint
import RPi.GPIO as GPIO
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

##### BUTTON ######
GPIO.setmode(GPIO.BOARD)
BUTTON_PIN = 12  # Change this to the GPIO pin you're using
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

class Teacher(db.Model, UserMixin):
    __tablename__ = 'teacher'
    id = db.Column(db.Integer, primary_key=True)

    lastname = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(255), nullable=False)
    middlename = db.Column(db.String(255))
    gender = db.Column(db.String(255), nullable=False)
    teacher_id = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    date_added = db.Column(db.DateTime, default=now)

    def __repr__(self):
        return '<Teacher %r>' % self.id

class Course(db.Model, UserMixin):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)

    course_name = db.Column(db.String(255), nullable=False)
    course_code = db.Column(db.String(255), nullable=False)
    course_description = db.Column(db.Text)
    course_units = db.Column(db.Integer)
    course_teacher = db.Column(db.String(255))
    date_added = db.Column(db.DateTime, default=now)

    def __repr__(self):
        return '<Courses %r>' % self.id
    
class Student(db.Model, UserMixin):
    __tablename__ = 'student'
    id = db.Column(db.Integer, primary_key=True)

    fingerprint_id = db.Column(db.Integer, nullable=False)
    lastname = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(255), nullable=False)
    middlename = db.Column(db.String(255))
    student_id = db.Column(db.String(255), unique=True, nullable=False)
    parent_phone = db.Column(db.String(255), nullable=False)
    teacher_name = db.Column(db.String(255), nullable=False)
    course_name = db.Column(db.String(255), nullable=False)
    date_added = db.Column(db.DateTime, default=now)

    def __repr__(self):
        return '<Student %r>' % self.id

class AttendanceHistory(db.Model, UserMixin):
    __tablename__ = 'attendacehistory'
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student_name = db.Column(db.String(1000), nullable=False)
    course = db.Column(db.String(255), nullable=False)
    course_teacher = db.Column(db.String(255), nullable=False)
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
    user1 = Teacher(lastname='Account', firstname='Admin', gender='Neutral', teacher_id='00000000', username='admin', password=hashed_password)
    db.session.add(user1)
    db.session.commit()
    print('Database seeded!')

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Teacher.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('error404'))

################ LOGIN/LOGOUT ################
@app.route('/', methods=["POST", "GET"])
def index():
    if current_user.is_authenticated:
        if current_user.username == 'admin':
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('dashboard'))
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        user = Teacher.query.filter_by(username=username.lower()).first()

        if user and check_password_hash(user.password, password):

            if user.username == 'admin':
                login_user(user)
                next_page = request.args.get('next')
                display.lcd_clear()
                display.lcd_display_string("Logging in...", 1)
                sleep(2)
                display.lcd_clear()
                return redirect(next_page or url_for('admin'))
            else:
                login_user(user)
                next_page = request.args.get('next')
                display.lcd_clear()
                display.lcd_display_string("Logging in...", 1)
                sleep(2)
                display.lcd_clear()
                return redirect(next_page or url_for('dashboard'))
        else:
            flash('Please check your login details and try again.')
            return redirect(url_for('index'))
                
    display.lcd_display_string("Student Attendance", 1)
    display.lcd_display_string("System", 2)
    display.lcd_display_string("Please login", 4)
    return render_template("login.html")

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
        courses = Course.query.filter_by(course_teacher=current_user.firstname+' '+current_user.lastname)
        students = Student.query.filter_by(teacher_name=current_user.firstname+' '+current_user.lastname).order_by(desc(Student.date_added)).all()
        histories = AttendanceHistory.query.filter_by(course_teacher=current_user.firstname+' '+current_user.lastname).order_by(desc(AttendanceHistory.date_timein)).all()
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Welcome Teacher", 3)
        display.lcd_display_string(f"{current_user.firstname + ' ' + current_user.lastname}", 4)
        return render_template("dashboard.html", fullname=current_user.firstname+' '+current_user.lastname, id=current_user.id, courses=courses, students=students, histories=histories)

@app.route('/attendance/<code>')
@login_required
def attendance_scan(code):
    if current_user.username == 'admin':
        return redirect(url_for('admin'))
    else:
        courses = Course.query.filter_by(course_teacher=current_user.firstname+' '+current_user.lastname)
        histories = AttendanceHistory.query.filter_by(course_teacher=current_user.firstname+' '+current_user.lastname)
        
        course_query = Course.query.filter_by(course_code=code).first()
                
        if course_query:
            coursename = course_query.course_name
            studentquery = Student.query.filter_by(course_name=coursename)

            today = now

            total_students = studentquery.count()
            check_present = AttendanceHistory.query.filter_by(course=coursename, date_timein=today, status='Present').count() == total_students

            if not check_present:
                for student in studentquery:
                    student_id = student.student_id
                    fullname = f"{student.firstname} {student.lastname}"
                    course = student.course_name
                    course_teacher = student.teacher_name

                    attendance = AttendanceHistory(
                        student_id=student_id,
                        student_name=fullname,
                        course=course,
                        course_teacher=course_teacher,
                        status='Absent'
                    )

                    db.session.add(attendance)
                    db.session.commit()
            else:
                display.lcd_clear()
                display.lcd_display_string("All Students", 1)
                display.lcd_display_string("are present.", 2)
                sleep(2)
                GPIO.cleanup()
                return redirect(url_for('index'))

        display.lcd_clear()
        display.lcd_display_string("Press button to", 1)
        display.lcd_display_string("take attendance", 2)
        sleep(2)
        while True:
            try:
                GPIO.wait_for_edge(BUTTON_PIN, GPIO.FALLING)
                display.lcd_clear()
                display.lcd_display_string("Button pressed.", 2)
                sleep(2)
                if studentquery.count() > 0:
                    if get_fingerprint():
                        students = studentquery.filter_by(fingerprint_id=finger.finger_id).first()
                        number = students.parent_phone
                        studentid = students.student_id
                        fullname = students.firstname+' '+students.lastname
                        course = students.course_name
                        course_teacher = students.teacher_name
                        attendance = AttendanceHistory.query.filter_by(student_id=studentid, student_name=fullname, course=course, course_teacher=course_teacher, date_timein=today).first()

                        if attendance:
                            attendance.status = 'Present'

                            db.session.commit()

                            if open_serial_port():
                                try:
                                    response = send_at_command('AT\r')
                                    print("AT Command response:", response)

                                    response = send_at_command('AT+CMGF=1\r')
                                    print("CMGF response:", response)

                                    response = send_at_command(f'AT+CMGS="{number}"\r')
                                    print("CMGS response:", response)

                                    response = send_at_command(f'Your child, {fullname}, has entered their {course} class. The time is {attendance.date_timein}. \x1A')
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
                    return redirect(url_for('attendance_scan', code=code))
                else:
                    display.lcd_clear()
                    display.lcd_display_string("No student found.", 1)
                    sleep(2)
                    return redirect(url_for('attendance_scan', code=code))
            except KeyboardInterrupt:
                GPIO.cleanup()
                sys.exit()

        return render_template("attendance.html", courses=courses, histories=histories)
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
    display.lcd_clear()
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
    display.lcd_clear()
    display.lcd_display_string("Searching", 1)
    if finger.finger_search() != adafruit_fingerprint.OK:
        display.lcd_clear()
        display.lcd_display_string("Not found.", 1)
        sleep(1)
        return False

    display.lcd_clear()
    display.lcd_display_string("Success", 1)
    return True

@app.route('/students/add', methods=["POST", "GET"])
@login_required
def students_add():
    MAX_FINGERPRINT_ID = 162
    courses = Course.query.filter_by(course_teacher=current_user.firstname+' '+current_user.lastname)

    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            studentid = request.form.get('student_id')
            lastname = request.form.get('lastname')
            firstname = request.form.get('firstname')
            middlename = request.form.get('middlename')
            course = request.form.get('course_name')
            parentphone = request.form.get('parentphone')

            #Checking
            student_check = Student.query.filter_by(student_id=studentid).first()
            
            if student_check:
                flash('Student Exists. Try again.')
                display.lcd_clear()
                display.lcd_display_string("Student Exists", 1)
                display.lcd_display_string("Try again.", 2)
                sleep(2)
                return redirect(url_for('students_add'))

            # Check if the fingerprint_id is available
            available_fingerprint = None
            existing_students = Student.query.all()
            all_fingerprint_ids = set(student.fingerprint_id for student in existing_students)

            for i in range(1, MAX_FINGERPRINT_ID + 1):
                if i not in all_fingerprint_ids:
                    available_fingerprint = i
                    break

            if available_fingerprint is None:
                return "No available fingerprint_id, cannot add a new student."

            # Commit Data into Database
            new_student = Student(lastname=lastname, firstname=firstname, middlename=middlename, course_name=course, student_id=studentid, teacher_name=current_user.firstname+' '+current_user.lastname, parent_phone=parentphone, fingerprint_id=available_fingerprint)

            db.session.add(new_student)
            db.session.commit()

            # Query into Students and get ID
            query = Student.query.filter_by(student_id=studentid).first()

            location = query.fingerprint_id
            
            # Wait for a finger to be read
            enroll(location)
            sleep(2)
            display.lcd_clear()

            return redirect(url_for('index'))
            
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
        elif i == adafruit_fingerprint.ENROLLMISMATCH:
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
    courses = Course.query.all()
    student = Student.query.get_or_404(id)

    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        if request.method == "POST":
            student.student_id = request.form.get('studentid')
            student.lastname = request.form.get('lastname')
            student.firstname = request.form.get('firstname')
            student.middlename = request.form.get('middlename')
            student.course_name = request.form.get('coursename')
            student.parent_phone = request.form.get('parentphone')

            db.session.commit()

            return redirect(url_for('index'))
            
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Students Update", 4)
        return render_template("students-update.html", courses=courses, student=student)


@app.route('/students/delete/<id>')
@login_required
def students_delete(id):
    student = Student.query.get_or_404(id)
    if current_user.username == 'admin':
        return redirect(url_for('admin'))
    else:
        display.lcd_clear()
        display.lcd_display_string("Deleting Student", 1)
        display.lcd_display_string(f"{ student.firstname+' '+student.lastname }", 2)
        sleep(2)

        if finger.delete_model(student.fingerprint_id) == adafruit_fingerprint.OK:
            display.lcd_clear()
            display.lcd_display_string("Student Fingerprint", 1)
            display.lcd_display_string("Deleted...", 2)
            sleep(2)

        history = None

        if student:
            history = AttendanceHistory.query.filter_by(student_id=student.student_id).first()

        if history:
            db.session.delete(history)

        db.session.delete(student)

        display.lcd_clear()
        display.lcd_display_string("Student Deleted...", 1)
        sleep(2)

        db.session.commit()

        return redirect(url_for('index'))

    return redirect(url_for('index'))

##### FOR DEBUG PURPOSES ####
## THIS CLEARS ALL FINGERPRINT IN THE SENSOR LIBRARY ##
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
################ ADMIN DASHBOARD ################
@app.route('/admin')
@login_required
def admin():
    if current_user.username == 'admin':
        teacher = Teacher.query.filter(Teacher.username!='admin').all()
        course = Course.query.all()
        student = Student.query.all()

        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Welcome Admin", 4)

        return render_template("admin.html", fullname=current_user.firstname, teacher=teacher, course=course, student=student)
    else:
        return redirect(url_for('index'))

################ COURSES ################
@app.route('/courses/add', methods=["POST", "GET"])
@login_required
def addcourse():
    if current_user.username == 'admin':
        teacher_query = Teacher.query.filter(Teacher.username!='admin')

        if teacher_query.count() > 0:
            if request.method == "POST":
                course_name = request.form.get('coursename')
                course_code = request.form.get('coursecode')
                course_description = request.form.get('coursedescription')
                course_units = request.form.get('courseunits')
                course_teacher = request.form.get('courseteacher')
                #Checking
                course_check = Course.query.filter_by(course_code=course_code).first()
                
                if course_check:
                    flash('Course Exists. Try again.')
                    display.lcd_clear()
                    display.lcd_display_string("Course Exists", 1)
                    display.lcd_display_string("Try again.", 2)
                    sleep(2)
                    return redirect(url_for('courses_add'))
                new_course = Course(course_name=course_name, course_code=course_code, course_description=course_description, course_units=course_units, course_teacher=course_teacher)

                display.lcd_clear()
                display.lcd_display_string("Adding course...", 1)
                sleep(2)

                db.session.add(new_course)
                db.session.commit()

                display.lcd_clear()
                display.lcd_display_string("Course Added", 1)
                sleep(2)

                return redirect(url_for('admin'))
        else:
            flash('Add a Teacher First before proceeding to add course.')
        teachers = Teacher.query.filter(Teacher.username!='admin').all()
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("", 3)
        display.lcd_display_string("Add Course", 4)
        return render_template("courses-add.html", teachers=teachers, fullname=current_user.firstname+' '+current_user.lastname)
    else:
        return redirect(url_for('admin'))

@app.route('/courses/delete/<id>')
@login_required
def deletecourse(id):
    if current_user.username == 'admin':
        course = Course.query.get(id)

        if course is None:
            abort(404)

        course_name = course.course_name
        students = Student.query.filter_by(course_name=course_name).all()

        display.lcd_clear()
        display.lcd_display_string("Deleting Course", 1)
        display.lcd_display_string(f"{course_name}", 2)
        sleep(2)
        
        if students:
            for student in students:
                db.session.delete(student)

        db.session.delete(course)

        display.lcd_clear()
        display.lcd_display_string("Course Deleted...", 1)
        sleep(2)

        db.session.commit()

        return redirect(url_for('index'))
    return redirect(url_for('index'))

################ TEACHERS ################
@app.route('/teachers/add', methods=["POST", "GET"])
@login_required
def addteacher():
    if current_user.username == 'admin':
        if request.method == "POST":
            
            random_numbers = ''.join(random.choices(string.digits, k=4))

            teacher_id = request.form.get('teacher_id')
            lastname = request.form.get('lastname')
            firstname = request.form.get('firstname')
            middlename = request.form.get('middlename')
            gender = request.form.get('gender')
            username = lastname.lower() + firstname[0].lower() + random_numbers
            password = request.form.get('password')

            user = Teacher.query.filter_by(teacher_id=teacher_id).first()
            
            if user:
                flash('Teacher Exists. Try again.')
                display.lcd_clear()
                display.lcd_display_string("Teacher Exists", 1)
                display.lcd_display_string("Try again.", 2)
                sleep(2)
                return redirect(url_for('addteacher'))
            
            new_user = Teacher(teacher_id=teacher_id, lastname=lastname, firstname=firstname, middlename=middlename, gender=gender, username=username, password=generate_password_hash(password))
            
            display.lcd_clear()
            display.lcd_display_string("Adding Teacher...", 1)
            sleep(2)

            db.session.add(new_user)
            db.session.commit()
            
            display.lcd_clear()
            display.lcd_display_string("Teacher Added", 1)
            sleep(2)
            
            return redirect(url_for('index'))
        display.lcd_clear()
        display.lcd_display_string("Student Attendance", 1)
        display.lcd_display_string("System", 2)
        display.lcd_display_string("Add Teacher", 4)
        return render_template("addteacher.html", fullname=current_user.firstname+' '+current_user.lastname)
    return redirect(url_for('index'))

@app.route('/teachers/update/<id>', methods=["POST", "GET"])
@login_required
def updateteacher(id):
    if current_user.username == 'admin':
        teacher = Teacher.query.get_or_404(id)

        if request.method == "POST":
            random_numbers = ''.join(random.choices(string.digits, k=4))
            teacher.lastname = request.form['lastname']
            teacher.firstname = request.form['firstname']
            teacher.middlename = request.form['middlename']
            teacher.gender = request.form['gender']
            teacher.username = teacher.lastname.lower() + teacher.firstname[0].lower() + random_numbers
            teacher.password = generate_password_hash(request.form['password'])

            display.lcd_clear()
            display.lcd_display_string("Updating Teacher", 1)
            sleep(2)

            db.session.commit()

            display.lcd_clear()
            display.lcd_display_string("Teacher Updated", 1)
            sleep(2)

            return redirect(url_for('index'))
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
        teacher = Teacher.query.get(id)
        if teacher is None:
            abort(404)  # Return 404 Not Found error page
        
        # Find all students associated with the teacher
        teacher_name = teacher.firstname + ' ' + teacher.lastname
        students = Student.query.filter_by(teacher_name=teacher_name).all()
        courses = Course.query.filter_by(course_teacher=teacher_name).all()

        display.lcd_clear()
        display.lcd_display_string("Deleting Teacher", 1)
        display.lcd_display_string(f"{teacher.firstname+' '+teacher.lastname}", 2)
        sleep(2)

        for course in courses:
            db.session.delete(course)
        
        for student in students:
            if student.fingerprint_id:
                # Delete the student's fingerprint ID
                if finger.delete_model(student.fingerprint_id) == adafruit_fingerprint.OK:
                    display.lcd_clear()
                    display.lcd_display_string("Student Fingerprints", 1)
                    display.lcd_display_string("Deleted...", 2)
                    sleep(2)

            # Delete the student's history if it exists
            history = History.query.filter_by(studentid=student.studentid).first()
            if history:
                db.session.delete(history)

            # Delete the student from the database
            db.session.delete(student)
        
        # Delete the teacher from the database
        db.session.delete(teacher)
        
        display.lcd_clear()
        display.lcd_display_string("Teacher Deleted...", 1)
        sleep(2)

        db.session.commit()

        return redirect(url_for('index'))
    
    return redirect(url_for('index'))

@app.route('/error404')
@login_required
def error404():
    return render_template("error404.html")

#404 ERROR HANDLING
@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for('error404'))