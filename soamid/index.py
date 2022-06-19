from flask import *
from flask_mail import *
from itsdangerous import *
from flask_mongoengine import MongoEngine
import hashlib, json

#----------
#	INIT
#----------
app = Flask(__name__, template_folder="template")
app.secret_key = "Essay";

#CONFIGURE MAIL INFO
app.config.from_pyfile('config.cfg')
mailConfig = Mail(app)
SecretKey = URLSafeTimedSerializer("SecretKey")
sender = "soa13526@gmail.com";

#---------------
#	DATABASE
#---------------
app.config['MONGODB_SETTINGS'] = {
    'db': 'tuitionFees',
    'host': 'localhost',
    'port': 27017
}
db = MongoEngine()
db.init_app(app)

# Bảng user
class User(db.Document):
	hoTenSV = db.StringField()
	soDienThoai = db.StringField()
	email = db.StringField()
	tenNguoiDung = db.StringField()
	matKhau = db.StringField()
	soDuTK = db.FloatField()
	lichSuGiaoDich= db.ListField()


# Bảng tuition fees
class TuitionFees(db.Document):
	mssv = db.StringField()
	tenSinhVien = db.StringField()
	hocPhi = db.FloatField()
	trangThaiThanhToan = db.StringField()
	lichSuThanhToan = db.DictField()

@app.route('/')
def index():
	return render_template('home.html')

# Đăng nhập
@app.route('/signup',methods=["GET","POST"])
def LogIn():
	if "user" in session and "hoTenSV" in session:
		g.hoTenSV = session["hoTenSV"];
		g.email = session["email"];
		g.soDienThoai = session["soDienThoai"];
		user = User.objects(email = g.email).first()
		return render_template('tuitionpayment.html', soDuTK = user.soDuTK)
	if(request.method=="POST"):
		TENNGUOIDUNG 	= request.form['tenNguoiDung'];
		PASSWORD 	= request.form['matKhau'];

		# Lấy thông tin từ database
		user = User.objects(tenNguoiDung = TENNGUOIDUNG, matKhau = PASSWORD).first()
		if user:
			session["user"] = user.tenNguoiDung;
			session["hoTenSV"] = user.hoTenSV;
			session["email"] = user.email;
			session["soDienThoai"] = user.soDienThoai;
			session["soDuTK"] = user.soDuTK;

			g.hoTenSV = session["hoTenSV"];
			g.email = session["email"];
			g.soDienThoai = session["soDienThoai"];
			return render_template('tuitionpayment.html', soDuTK = user.soDuTK)
		return render_template('signup.html', errorMessage = 'Tên tài khoản hoặc mật khẩu không chính xác!')
	if request.method == "GET":
		return render_template('signup.html')

# OTP email
@app.route('/otp',methods=["GET","POST"])
def otp():
	if(request.method=="POST"):
		Title 		= "HocPhi";
		recipients 	= request.form['email'];
		OTP 		= SecretKey.dumps(recipients, salt="email-confirm")
		mess 		= Message(Title, sender=sender, recipients=[recipients])
		mess.body 	= "Hi {}! \nYour OTP: {}".format(recipients.split("@gmail.com")[0], OTP)
		mailConfig.send(mess)

		# Receive transaction data from the form
		ten = request.form['ten']
		sdt = request.form['sdt']
		emailSV = request.form['email']
		mssv = request.form['MSSV']
		tenSinhVien = request.form['tenSV']
		hocPhi = request.form['hocPhi']
		soDu = request.form['soDu']
		soTienPhaiThanhToan = request.form['soTienPhaiThanhToan']
		tgian = request.form['tgian']

		ttinGiaoDich = {
			"ten": ten,
			"sdt": sdt,
			"emailSV": emailSV,
			"mssv": mssv,
			"tenSinhVien": tenSinhVien,
			"hocPhi": hocPhi,
			"soDu": soDu,
			"soTienPhaiThanhToan": soTienPhaiThanhToan,
			"tgian": tgian
		}
		session['ttinGiaoDich'] = ttinGiaoDich
		return render_template('otpvertification.html')
	else:
		return render_template('tuitionpayment.html')

# Confirm token và lưu trữ trên database
@app.route('/confirm',methods=["POST"])
def confirm():
	OTP = request.form['otp'];
	# Kiểm tra xem OTP có quá thời gian tồn tại hay không
	try:
		Email = SecretKey.loads(OTP, salt="email-confirm", max_age=300) # Đặt thời gian chờ lên đến 300 giây
	except SignatureExpired:
		g.messExpiredPayment = "Thời gian xác nhận than toán đã hết. Xin vui lòng thử lại.";
		return render_template('errorannounce.html')

	# Nếu không quá thời gian chờ => xác nhận OTP thành công và lưu vào database
	# Lấy thông tin giao dịch từ session
	ten = session['ttinGiaoDich']['ten']
	emailSV = session['ttinGiaoDich']['emailSV']
	mssv = session['ttinGiaoDich']['mssv']
	soDu = session['ttinGiaoDich']['soDu']
	soTienPhaiThanhToan = session['ttinGiaoDich']['soTienPhaiThanhToan']
	tgian = session['ttinGiaoDich']['tgian']

	# Cập nhật số dư tài khoản và lịch sử giao dịch của sinh viên
	nguoiThucHienGiaoDich = User.objects(email = emailSV).first()
	soDu = float("".join(soDu.split(",")))
	soTienPhaiThanhToan = float("".join(soTienPhaiThanhToan.split(",")))
	soDu_moi = soDu - soTienPhaiThanhToan
	lichSuGiaoDich_moi = nguoiThucHienGiaoDich.lichSuGiaoDich
	lichSuGiaoDich_moi.append({ "mssv": mssv, "soTienThanhToan": soTienPhaiThanhToan, "ngayThang": tgian })
	nguoiThucHienGiaoDich.update(soDuTK = soDu_moi, lichSuGiaoDich= lichSuGiaoDich_moi)

	# Cập nhật lịch sử thanh toán
	studentTF = TuitionFees.objects(mssv = mssv, trangThaiThanhToan = "noHocPhi").first()
	studentTF.update(trangThaiThanhToan = "Đã thanh toán", lichSuThanhToan = { "nguoiThucHienGiaoDich": ten, "ngayThang": tgian })

	# Gửi mail đến sinh viên thông báo thanh toán thành công
	Title 		= "HocPhi"
	recipients 	= emailSV
	mess 		= Message(Title, sender = sender, recipients = [recipients])
	successfulMessage = "\nThanh toán thành công.\n\nChi tiết:\nTên sinh viên: {}\nSố tiền còn lại: {:,.2f}\nMã số sinh viên: {}\nSố tiền đã thanh toán: {:,.2f}\nThời gian: {}".format(ten, soDu_moi, mssv, soTienPhaiThanhToan, tgian)
	mess.body 	= "Hi {}! \n{}".format(recipients.split("@gmail.com")[0], successfulMessage)
	mailConfig.send(mess)
	return redirect(url_for('Announce'))

# Thông báo kiểm tra mail
@app.route('/announce')
def Announce():
	if "user" in session and "hoTenSV" in session:
		emailSV = session['ttinGiaoDich']['emailSV']
		return render_template("paymentsuccess.html", emailSV = emailSV)
	else:
		return render_template('signup.html')

# Lấy thông tin sinh viên
@app.route("/student/<id>", methods=['GET'])
def getStudentData(id):
	if request.method == "GET":
		studentTF = TuitionFees.objects(mssv = id, trangThaiThanhToan = "noHocPhi").first()
		return jsonify(studentTF)

# Đăng xuất
@app.route('/logout')
def LogOut():
	session.pop('user', None)
	session.pop('hoTenSV', None)
	session.pop('email', None)
	session.pop('soDienThoai', None)
	session.pop('soDuTK', None)
	return redirect(url_for('LogIn'))

# 404 NOT FOUND
@app.errorhandler(404)
def HandleNotFound(e):
	g.mess404NotFound = "404 not found";
	return render_template('errorannounce.html')

# 400 BAD REQUEST
@app.errorhandler(400)
def HandleBadRequest(e):
	g.mess400BadRequest = "400 bad request";
	return render_template('errorannounce.html')

if(__name__ == "__main__"):
	app.run()
