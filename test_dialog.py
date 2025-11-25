import sys
from PyQt6.QtWidgets import QApplication
from gui import RegisterDialog

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = RegisterDialog()
    print("对话框创建完成")
    result = dialog.exec()
    print(f"对话框结果: {result}")
    if result == dialog.DialogCode.Accepted:
        username, email, password = dialog.get_credentials()
        print(f"用户名: {username}")
        print(f"邮箱: {email}")
        print(f"密码长度: {len(password)}")
    else:
        print("用户取消")