from flask import Flask, render_template, url_for, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from time import sleep
import drivers
import serial
import adafruit_fingerprint
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SECRET_KEY'] = 'g1mo9je(e9jo0uv+(8(^1fl31dd%$5rldf04zm$^20am)z=c(h'
db = SQLAlchemy(app)


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
    date_added = db.Column(db.Date, default=date.today)

    def __repr__(self):
        return '<User %r>' % self.id

class Courses(db.Model, UserMixin):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)

    course_name = db.Column(db.String(255), nullable=False)
    course_code = db.Column(db.String(255), nullable=False)
    course_description = db.Column(db.String(1000), nullable=False)
    course_units = db.Column(db.String(255), nullable=False)
    course_year = db.Column(db.String(255), nullable=False)
    course_teacher = db.Column(db.ForeignKey('user.fullname'), nullable=False)
    date_added = db.Column(db.Date, default=date.today)

    teacher = db.Relationship('User', foreign_keys=course_teacher)
    def __repr__(self):
        return '<Courses %r>' % self.id
    
class Students(db.Model, UserMixin):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)

    fullname = db.Column(db.String(1000), nullable=False)
    course = db.Column(db.String(255), nullable=False)
    studentid = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(255), nullable=False)
    program = db.Column(db.String(255), nullable=False)
    year = db.Column(db.String(255), nullable=False)
    parentphone = db.Column(db.String(255), nullable=False)
    teacher_name = db.Column(db.String(1000), db.ForeignKey('user.fullname'), nullable=False)
    date_added = db.Column(db.Date, default=date.today)

    teacher = db.Relationship('User', foreign_keys=teacher_name)

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
    date_timein = db.Column(db.DateTime, default=datetime.now)
    
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
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Please check your login details and try again.')

    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

################ TEACHER DASHBOARD ################
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        return render_template("dashboard.html", fullname=current_user.fullname)

################ HISTORY ################
@app.route('/history')
@login_required
def history():
    if current_user.username == 'admin':
            return redirect(url_for('admin'))
    else:
        histories = History.query.all()

        return render_template("history.html", histories=histories)
################ ATTENDANCE ################
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
        students = Students.query.filter_by(teacher_name=current_user.fullname).order_by(Students.date_added).all()

        return render_template("students-db.html", students=students)

@app.route('/students/add', methods=["POST", "GET"])
@login_required
def students_add():
    courses = Courses.query.all()

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

            # Commit Data into Database
            new_student = Students(fullname=fullname, course=course, studentid=studentid, department=department, program=program, year=year, teacher_name=current_user.fullname, parentphone=parentphone)

            db.session.add(new_student)
            db.session.commit()

            # Query into Students and get ID
            query = Students.query.filter_by(fullname=fullname).first()

            location = query.id
            
            # Wait for a finger to be read
            enroll(location)
            sleep(2)
            display.lcd_clear()

            return redirect(url_for('students_list'))
        return render_template("students-add.html", courses=courses)

#Fingerprint Enroll
def enroll(location):
    for fingerimg in range(1, 3):
        if fingerimg == 1:
            display.lcd_display_string("Place finger", 1)
        else:
            display.lcd_display_string("Place again", 1)

        while True:
            i = finger.get_image()
            if i == adafruit_fingerprint.OK:
                display.lcd_display_string("Image taken", 1)
                break
            if i == adafruit_fingerprint.NOFINGER:
                display.lcd_display_string(".", 1)
            elif i == adafruit_fingerprint.IMAGEFAIL:
                display.lcd_display_string("Imaging error", 1)
            else:
                display.lcd_display_string("Other error", 1)
            # Add a delay here to allow the user to see the error message
            sleep(2)
            display.lcd_clear()

        display.lcd_display_string("Templating...", 1)
        i = finger.image_2_tz(fingerimg)
        if i == adafruit_fingerprint.OK:
            display.lcd_display_string("Templated", 1)
        else:
            if i == adafruit_fingerprint.IMAGEMESS:
                display.lcd_display_string("Image too messy", 1)
            elif i == adafruit_fingerprint.FEATUREFAIL:
                display.lcd_display_string("Could not identify features", 1)
            elif i == adafruit_fingerprint.INVALIDIMAGE:
                display.lcd_display_string("Image invalid", 1)
            else:
                display.lcd_display_string("Other error", 1)
            # Add a delay here to allow the user to see the error message
            sleep(2)
            display.lcd_clear()

        if fingerimg == 1:
            display.lcd_display_string("Remove finger", 1)
            sleep(1)
            while i != adafruit_fingerprint.NOFINGER:
                i = finger.get_image()

    display.lcd_display_string("Creating model...", 1)
    i = finger.create_model()
    if i == adafruit_fingerprint.OK:
        display.lcd_display_string("Created", 1)
    else:
        if i == adafruit_fingerprint.ENROLLMISMATCH:
            display.lcd_display_string("Prints did not match", 1)
        else:
            display.lcd_display_string("Other error", 1)
        # Add a delay here to allow the user to see the error message
        sleep(2)
        display.lcd_clear()

    display.lcd_display_string("Storing model #%d..." % location, 1)
    i = finger.store_model(location)
    if i == adafruit_fingerprint.OK:
        display.lcd_display_string("Stored", 1)
    else:
        if i == adafruit_fingerprint.BADLOCATION:
            display.lcd_display_string("Bad storage location", 1)
        elif i == adafruit_fingerprint.FLASHERR:
            display.lcd_display_string("Flash storage error", 1)
        else:
            display.lcd_display_string("Other error", 1)
        # Add a delay here to allow the user to see the error message
        sleep(2)
        display.lcd_clear()

    return True

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
            course_year = request.form.get('course_year')

            new_course = Courses(course_name=course_name, course_code=course_code, course_description=course_description, course_units=course_units, course_year=course_year, course_teacher=current_user.fullname)

            db.session.add(new_course)
            db.session.commit()

            return redirect(url_for('courses'))
        return render_template("courses-add.html")
    
################ ADMIN DASHBOARD ################
@app.route('/admin')
@login_required
def admin():
    return render_template("admin.html", fullname=current_user.fullname)

@app.route('/teachers')
@login_required
def teachers():
    teachers = User.query.all()

    return render_template("teachers.html", teachers=teachers)

@app.route('/teachers/add', methods=["POST", "GET"])
@login_required
def addteacher():
    if request.method == "POST": 
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        
        if user:
            flash('Username Exists. Try another one.')
            return redirect(url_for('addteacher'))
        
        new_user = User(fullname=fullname, username=username.lower(), password=generate_password_hash(password, method='sha256'))

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('teachers'))
    return render_template("addteacher.html")

@app.route('/students')
@login_required
def students():
    students = Students.query.order_by(Students.date_added).all()

    return render_template("students.html", students=students)