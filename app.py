
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "secret_key"

# DATABASE CONNECTION 
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="agastya@13",
    database="student_db",
    
)
cursor = db.cursor(dictionary=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template('login1.html')

    username = request.form['username'].strip()
    password = request.form['password'].strip()

    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()

    if user:
        session['username'] = user['username']
        session['role'] = user['role']
        session['student_id'] = user.get('student_id') 

        if user['role'] == 'teacher':
            session['teacher_id'] = user['id']
            return redirect(url_for('teacher_dashboard'))

        elif user['role'] == 'student':
            return redirect(url_for('student_dashboard'))

    else:
        flash("Invalid username or password. Try again.")
        return render_template('login1.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Student routes
@app.route('/student')
def student_dashboard():
    if 'role' in session and session['role'] == 'student':
        username = session['username']
        cursor.execute("""
            SELECT s.id, s.name, s.class, s.rollno, s.age
            FROM students s
            JOIN users u ON u.student_id = s.id
            WHERE u.username = %s
        """, (username,))
        student_info = cursor.fetchone()

        if not student_info:
            return "<h3>No linked student record found.</h3>"

        return render_template('student.html', username=username, student_info=student_info)
    return redirect(url_for('login'))

@app.route('/student/attendance')
def student_attendance():
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    student_id = session.get('student_id')
    if not student_id:
        return "<h3>No linked student record.</h3>"
    cursor.execute("SELECT date, status FROM attendance WHERE student_id=%s ORDER BY date DESC", (student_id,))
    attendance = cursor.fetchall()
    return render_template('attendancestudent.html', attendance=attendance)

@app.route('/student/marks')
def student_marks():
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    student_id = session.get('student_id')
    if not student_id:
        return "<h3>No linked student record.</h3>"

    cursor.execute("""
        SELECT subjects.subject_name AS subject, marks.marks
        FROM marks
        JOIN subjects ON marks.subject_id = subjects.id
        WHERE marks.student_id = %s
    """, (student_id,))
    marks = cursor.fetchall()

    # Calculate totals
    total = sum([m['marks'] for m in marks]) if marks else 0
    num_subj = len(marks)
    percentage = round((total / (num_subj * 100) * 100), 2) if num_subj else 0
    cgpa = round(percentage / 9.5, 2) if num_subj else 0

    # Get class for ranking
    cursor.execute("SELECT class FROM students WHERE id=%s", (student_id,))
    clsrow = cursor.fetchone()

    rank = None
    if clsrow:
        cls = clsrow['class']

        # Ranking based on total marks in class
        cursor.execute("""
            SELECT m.student_id, SUM(m.marks) AS total_marks
            FROM marks m
            JOIN students s ON s.id = m.student_id
            GROUP BY m.student_id, s.class
            HAVING s.class = %s
            ORDER BY total_marks DESC
        """, (cls,))
        rows = cursor.fetchall()

        last_total = None
        r = 0
        skip = 0
        for row in rows:
            if last_total is None or row['total_marks'] != last_total:
                r += skip + 1
                skip = 0
            else:
                skip += 1
            last_total = row['total_marks']

            if row['student_id'] == student_id:
                rank = r
                break

    return render_template(
        'mrksstu.html',
        marks=marks,
        total=total,
        num_subjects=num_subj,
        percentage=percentage,
        cgpa=cgpa,
        rank=rank
    )


@app.route('/student/feedback')
def student_feedback():
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    student_id = session['student_id']

    cursor.execute("""
        SELECT u.username AS teacher_name, f.feedback_text, f.feedback_date
        FROM feedback f
        JOIN users u ON f.teacher_id = u.id
        WHERE f.student_id = %s
        ORDER BY f.feedback_date DESC
    """, (student_id,))
    feedbacks = cursor.fetchall()

    return render_template("student_feedback.html", feedbacks=feedbacks)

# Teacher routes 
@app.route('/teacher')
def teacher_dashboard():
    if 'role' in session and session['role'] == 'teacher':
        cursor.execute("SELECT id, name, class, rollno FROM students ORDER BY class, rollno")
        students = cursor.fetchall()
        return render_template('teacher.html', username=session['username'], students=students)
    return redirect(url_for('login'))

@app.route('/teacher/attendance', methods=['GET','POST'])
def teacher_attendance():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        status = request.form['status']
        att_date = request.form.get('date') or date.today().isoformat()
        cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (%s,%s,%s)",
                       (student_id, att_date, status))
        db.commit()
        flash("Attendance recorded.")
        return redirect(url_for('teacher_attendance'))

    cursor.execute("""SELECT a.id, a.student_id, a.date, a.status, s.name
                      FROM attendance a JOIN students s ON s.id = a.student_id
                      ORDER BY a.date DESC""")
    attendance = cursor.fetchall()

    cursor.execute("SELECT id, name FROM students ORDER BY class, rollno")
    students = cursor.fetchall()
    return render_template('attendanceteacher.html', attendance=attendance, students=students)

@app.route('/teacher_marks', methods=['GET', 'POST'])
def teacher_marks():
    if request.method == 'POST':
        student_id = request.form['student_id']
        subject_name = request.form['subject']
        marks = request.form['marks']

  
        cursor.execute("SELECT id FROM subjects WHERE subject_name = %s", (subject_name,))
        subject_row = cursor.fetchone()

        subject_id = subject_row['id']

      
        cursor.execute("""
            INSERT INTO marks (student_id, subject_id, marks)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE marks = VALUES(marks)
        """, (student_id, subject_id, marks))
        db.commit()

        return redirect(url_for('teacher_marks'))

    cursor.execute("SELECT id, name FROM students")
    students = cursor.fetchall()

    cursor.execute("SELECT subject_name FROM subjects")
    subjects = cursor.fetchall()

    return render_template("marks_teacher.html", students=students, subjects=subjects)


@app.route('/teacher/feedback', methods=['GET', 'POST'])
def teacher_feedback():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    teacher_id = session.get('teacher_id')  
    if not teacher_id:
        return "Teacher ID missing in session"

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        feedback_text = request.form.get('feedback_text')

        cursor.execute(
            "INSERT INTO feedback (student_id, teacher_id, feedback_text) VALUES (%s, %s, %s)",
            (student_id, teacher_id, feedback_text)
        )
        db.commit()
        return redirect(url_for('teacher_feedback'))


    cursor.execute("SELECT id, name FROM students")
    students = cursor.fetchall()


    cursor.execute("""
        SELECT f.feedback_text, f.feedback_date, s.name AS student_name, u.username AS teacher_name
        FROM feedback f
        LEFT JOIN students s ON f.student_id = s.id
        LEFT JOIN users u ON f.teacher_id = u.id
        ORDER BY f.feedback_date DESC
    """)
    feedback_list = cursor.fetchall()

    return render_template("teacher_feedback.html", students=students, feedbacks=feedback_list)


if __name__ == "__main__":
    app.run(debug=True)
