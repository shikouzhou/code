import sys
import json
import requests
import mysql.connector
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox, QSplitter, QGroupBox, QDialog, QFormLayout,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt

class SchemaGeneratorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.current_schema = None
        self.current_ddl = None
        self.current_session_id = None
        self.access_token = None
        self.current_user = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('数据库模式生成器')
        self.setGeometry(100, 100, 1200, 800)

        layout = QVBoxLayout()

        # 认证状态栏
        auth_layout = QHBoxLayout()
        self.auth_label = QLabel("未登录")
        auth_layout.addWidget(self.auth_label)

        self.login_btn = QPushButton("登录")
        self.login_btn.clicked.connect(self.show_login_dialog)
        auth_layout.addWidget(self.login_btn)

        self.register_btn = QPushButton("注册")
        self.register_btn.clicked.connect(self.show_register_dialog)
        auth_layout.addWidget(self.register_btn)

        self.logout_btn = QPushButton("登出")
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setEnabled(False)
        auth_layout.addWidget(self.logout_btn)

        self.history_btn = QPushButton("历史记录")
        self.history_btn.clicked.connect(self.show_history_dialog)
        self.history_btn.setEnabled(False)
        auth_layout.addWidget(self.history_btn)

        auth_layout.addStretch()
        layout.addLayout(auth_layout)

        # 主标签页
        self.tab_widget = QTabWidget()

        # 生成模式标签页
        generate_tab = QWidget()
        generate_layout = QVBoxLayout()

        # 输入区域
        input_group = QGroupBox("自然语言描述")
        input_layout = QVBoxLayout()
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入自然语言描述，如：我要做一个校园二手交易平台，有用户、商品、订单，用户可以发布商品，其他人可以下单购买")
        input_layout.addWidget(self.input_text)

        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成模式")
        self.generate_btn.clicked.connect(self.generate_schema)
        self.generate_btn.setEnabled(False)  # 默认禁用，需要登录
        button_layout.addWidget(self.generate_btn)

        self.edit_btn = QPushButton("编辑模式")
        self.edit_btn.clicked.connect(self.edit_schema)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)

        self.modify_btn = QPushButton("修改实体")
        self.modify_btn.clicked.connect(self.modify_entities)
        self.modify_btn.setEnabled(False)
        button_layout.addWidget(self.modify_btn)

        input_layout.addLayout(button_layout)
        input_group.setLayout(input_layout)
        generate_layout.addWidget(input_group)
        # 显示区域
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：E-R模型和关系模式
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        er_group = QGroupBox("E-R模型")
        self.er_text = QTextEdit()
        self.er_text.setReadOnly(True)
        er_layout = QVBoxLayout()
        er_layout.addWidget(self.er_text)
        er_group.setLayout(er_layout)
        left_layout.addWidget(er_group)

        relational_group = QGroupBox("关系模式")
        self.relational_text = QTextEdit()
        self.relational_text.setReadOnly(True)
        relational_layout = QVBoxLayout()
        relational_layout.addWidget(self.relational_text)
        relational_group.setLayout(relational_layout)
        left_layout.addWidget(relational_group)

        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # 右侧：DDL
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        ddl_group = QGroupBox("MySQL DDL")
        self.ddl_text = QTextEdit()
        self.ddl_text.setReadOnly(True)
        ddl_layout = QVBoxLayout()
        ddl_layout.addWidget(self.ddl_text)

        self.execute_btn = QPushButton("执行SQL")
        self.execute_btn.clicked.connect(self.execute_sql)
        self.execute_btn.setEnabled(False)
        ddl_layout.addWidget(self.execute_btn)

        ddl_group.setLayout(ddl_layout)
        right_layout.addWidget(ddl_group)

        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        generate_layout.addWidget(splitter)
        generate_tab.setLayout(generate_layout)
        self.tab_widget.addTab(generate_tab, "生成模式")

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def update_auth_status(self):
        """更新认证状态显示"""
        if self.access_token and self.current_user:
            self.auth_label.setText(f"已登录: {self.current_user}")
            self.login_btn.setEnabled(False)
            self.register_btn.setEnabled(False)
            self.logout_btn.setEnabled(True)
            self.history_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)
            self.modify_btn.setEnabled(True)
        else:
            self.auth_label.setText("未登录")
            self.login_btn.setEnabled(True)
            self.register_btn.setEnabled(True)
            self.logout_btn.setEnabled(False)
            self.history_btn.setEnabled(False)
            self.generate_btn.setEnabled(False)

    def show_login_dialog(self):
        """显示登录对话框"""
        dialog = LoginDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username, password = dialog.get_credentials()
            self.login(username, password)

    def show_register_dialog(self):
        """显示注册对话框"""
        dialog = RegisterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username, email, password = dialog.get_credentials()
            # 客户端验证
            if not username or len(username) < 3:
                QMessageBox.warning(self, "警告", "用户名至少需要3个字符")
                return
            if not email or "@" not in email:
                QMessageBox.warning(self, "警告", "请输入有效的邮箱地址")
                return
            if not password or len(password) < 6:
                QMessageBox.warning(self, "警告", "密码至少需要6位")
                return
            self.register(username, email, password)

    def login(self, username, password):
        """执行登录"""
        try:
            response = requests.post("http://localhost:8000/auth/login", json={"username": username, "password": password})
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.current_user = username
                self.update_auth_status()
                QMessageBox.information(self, "成功", "登录成功")
            else:
                QMessageBox.critical(self, "错误", f"登录失败: {response.json().get('detail', '未知错误')}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "错误", "无法连接到后端服务器")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")

    def register(self, username, email, password):
        """执行注册"""
        try:
            response = requests.post("http://localhost:8000/auth/register", json={"username": username, "email": email, "password": password})
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.current_user = username
                self.update_auth_status()
                QMessageBox.information(self, "成功", "注册成功，已自动登录")
            else:
                QMessageBox.critical(self, "错误", f"注册失败: {response.json().get('detail', '未知错误')}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "错误", "无法连接到后端服务器")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")

    def logout(self):
        """登出"""
        self.access_token = None
        self.current_user = None
        self.update_auth_status()
        self.modify_btn.setEnabled(False)
        QMessageBox.information(self, "成功", "已登出")

    def show_history_dialog(self):
        """显示历史记录对话框"""
        dialog = HistoryDialog(self.access_token, self)
        dialog.exec()

    def generate_schema(self):
        description = self.input_text.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "警告", "请输入自然语言描述")
            return

        if not self.access_token:
            QMessageBox.warning(self, "警告", "请先登录")
            return

        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post("http://localhost:8000/generate-schema", json={"description": description}, headers=headers)
            if response.status_code == 200:
                data = response.json()
                self.current_schema = data["schema"]
                self.current_ddl = data["ddl"]
                self.current_session_id = data["session_id"]
                self.display_results(data)
                self.edit_btn.setEnabled(True)
                self.modify_btn.setEnabled(True)
                QMessageBox.information(self, "成功", "模式生成成功")
            elif response.status_code == 401:
                QMessageBox.critical(self, "错误", "认证失败，请重新登录")
                self.logout()
            else:
                QMessageBox.critical(self, "错误", f"API调用失败: {response.status_code}\n{response.text}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "错误", "无法连接到后端服务器，请确保FastAPI应用正在运行")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")

    def display_results(self, data):
        # 显示E-R模型
        er_str = "实体:\n"
        for ent in data["er_model"]["entities"]:
            er_str += f"- {ent['name']}: {', '.join(ent['attributes'])} (主键: {ent['primary_key']})\n"
        er_str += "\n关系:\n"
        for rel in data["er_model"]["relationships"]:
            er_str += f"- {rel['name']}: {rel['entities']} ({rel['cardinality']})\n"
        self.er_text.setPlainText(er_str)

        # 显示关系模式（从DDL推断）
        relational_str = self.parse_ddl_to_relational(self.current_ddl)
        self.relational_text.setPlainText(relational_str)

        # 显示DDL
        self.ddl_text.setPlainText(self.current_ddl)
        self.execute_btn.setEnabled(True)

    def parse_ddl_to_relational(self, ddl):
        # 简单解析DDL显示表结构
        tables = ddl.strip().split(');\n\n')
        relational = ""
        for table_ddl in tables:
            if table_ddl.strip():
                lines = table_ddl.strip().split('\n')
                table_name = lines[0].replace('CREATE TABLE ', '').replace(' (', '')
                relational += f"表: {table_name}\n"
                for line in lines[1:]:
                    if line.strip() and not line.strip().startswith(')'):
                        relational += f"  {line.strip()}\n"
                relational += "\n"
        return relational

    def execute_sql(self):
        if not self.current_ddl:
            QMessageBox.warning(self, "警告", "没有可执行的DDL")
            return

        try:
            # 连接MySQL
            conn = mysql.connector.connect(
                host="localhost",
                user="appuser1",
                password="123！",
                database="db_generator"
            )
            cursor = conn.cursor()
            # 分割DDL并执行
            statements = [stmt.strip() for stmt in self.current_ddl.split(';') if stmt.strip()]
            for stmt in statements:
                if stmt:
                    cursor.execute(stmt)
            conn.commit()
            QMessageBox.information(self, "成功", "SQL执行成功")
        except mysql.connector.Error as e:
            QMessageBox.critical(self, "错误", f"MySQL错误: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行错误: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

    def edit_schema(self):
        if not self.current_schema:
            QMessageBox.warning(self, "警告", "没有可编辑的模式")
            return

        dialog = EditSchemaDialog(self.current_schema, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_schema = dialog.get_schema()
            # 重新生成ER模型、关系模式、DDL
            # 这里需要调用后端的逻辑，但前端没有，所以模拟或调用API重新生成
            # 为了简单，假设修改后重新调用generate_schema，但需要传递修改后的schema
            # 后端没有接受schema的端点，所以需要添加一个端点或在前端处理
            # 暂时用前端逻辑重新生成
            from schema_generator import build_er_model, convert_to_relational_schema, generate_mysql_ddl
            er_model = build_er_model(self.current_schema)
            relational_schema = convert_to_relational_schema(self.current_schema)
            ddl = generate_mysql_ddl(relational_schema)
            self.current_ddl = ddl
            # 构造data
            data = {
                "schema": self.current_schema,
                "er_model": {
                    "entities": [{"name": e.name, "attributes": e.attributes, "primary_key": e.primary_key} for e in er_model.entities],
                    "relationships": [{"name": r.name, "entities": r.entities, "cardinality": r.cardinality} for r in er_model.relationships]
                },
                "ddl": ddl
            }
            self.display_results(data)

    def modify_entities(self):
        """修改实体和关系"""
        if not self.current_schema or not self.current_session_id:
            QMessageBox.warning(self, "警告", "没有可修改的模式")
            return

        dialog = ModifyEntitiesDialog(self.current_schema, self.current_session_id, self.access_token, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 重新获取最新的schema
            self.refresh_current_schema()

    def refresh_current_schema(self):
        """重新获取当前session的schema"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"http://localhost:8000/user/history?skip=0&limit=1", headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data["records"]:
                    record = data["records"][0]
                    self.current_schema = record["schema_result"]
                    self.current_ddl = record["ddl_result"]
                    # 重新显示结果
                    display_data = {
                        "schema": self.current_schema,
                        "er_model": record["er_model_result"],
                        "ddl": self.current_ddl
                    }
                    self.display_results(display_data)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"刷新数据失败: {str(e)}")

class EditSchemaDialog(QDialog):
    def __init__(self, schema, parent=None):
        super().__init__(parent)
        self.schema = schema.copy()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("编辑模式")
        self.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout()

        # 实体列表
        entity_group = QGroupBox("实体")
        entity_layout = QVBoxLayout()
        self.entity_list = QListWidget()
        for ent in self.schema["entities"]:
            item = QListWidgetItem(f"{ent['name']}: {ent['attributes']} (PK: {ent['primary_key']})")
            item.setData(Qt.ItemDataRole.UserRole, ent)
            self.entity_list.addItem(item)
        entity_layout.addWidget(self.entity_list)

        add_entity_btn = QPushButton("添加实体")
        add_entity_btn.clicked.connect(self.add_entity)
        entity_layout.addWidget(add_entity_btn)

        entity_group.setLayout(entity_layout)
        layout.addWidget(entity_group)

        # 关系列表
        rel_group = QGroupBox("关系")
        rel_layout = QVBoxLayout()
        self.rel_list = QListWidget()
        for rel in self.schema["relationships"]:
            item = QListWidgetItem(f"{rel['name']}: {rel['entities']} ({rel['cardinality']})")
            item.setData(Qt.ItemDataRole.UserRole, rel)
            self.rel_list.addItem(item)
        rel_layout.addWidget(self.rel_list)

        add_rel_btn = QPushButton("添加关系")
        add_rel_btn.clicked.connect(self.add_relationship)
        rel_layout.addWidget(add_rel_btn)

        rel_group.setLayout(rel_layout)
        layout.addWidget(rel_group)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def add_entity(self):
        # 简单添加实体对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("添加实体")
        layout = QFormLayout()
        name_edit = QLineEdit()
        layout.addRow("名称:", name_edit)
        attr_edit = QLineEdit()
        layout.addRow("属性(逗号分隔):", attr_edit)
        pk_edit = QLineEdit()
        layout.addRow("主键:", pk_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            attrs = [a.strip() for a in attr_edit.text().split(',') if a.strip()]
            pk = pk_edit.text().strip()
            if name and attrs and pk:
                ent = {"name": name, "attributes": attrs, "primary_key": pk}
                self.schema["entities"].append(ent)
                item = QListWidgetItem(f"{name}: {attrs} (PK: {pk})")
                item.setData(Qt.ItemDataRole.UserRole, ent)
                self.entity_list.addItem(item)

    def add_relationship(self):
        # 简单添加关系对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("添加关系")
        layout = QFormLayout()
        name_edit = QLineEdit()
        layout.addRow("名称:", name_edit)
        entities_edit = QLineEdit()
        layout.addRow("实体(逗号分隔):", entities_edit)
        card_edit = QLineEdit()
        layout.addRow("基数:", card_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            entities = [e.strip() for e in entities_edit.text().split(',') if e.strip()]
            card = card_edit.text().strip()
            if name and entities and card:
                rel = {"name": name, "entities": entities, "cardinality": card}
                self.schema["relationships"].append(rel)
                item = QListWidgetItem(f"{name}: {entities} ({card})")
                item.setData(Qt.ItemDataRole.UserRole, rel)
                self.rel_list.addItem(item)

    def get_schema(self):
        return self.schema

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户登录")
        self.setGeometry(300, 300, 300, 200)

        layout = QFormLayout()
        self.username_edit = QLineEdit()
        layout.addRow("用户名:", self.username_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("密码:", self.password_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_credentials(self):
        return self.username_edit.text().strip(), self.password_edit.text().strip()


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户注册")
        self.setGeometry(300, 300, 300, 250)
        print("RegisterDialog初始化")  # 调试信息

        layout = QFormLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")
        layout.addRow("用户名:", self.username_edit)
        print("用户名字段创建")  # 调试信息

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("请输入邮箱地址")
        layout.addRow("邮箱:", self.email_edit)
        print("邮箱字段创建")  # 调试信息

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("请输入密码")
        layout.addRow("密码:", self.password_edit)
        print("密码字段创建")  # 调试信息

        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_edit.setPlaceholderText("请再次输入密码")
        layout.addRow("确认密码:", self.confirm_password_edit)
        print("确认密码字段创建")  # 调试信息

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        print("按钮创建")  # 调试信息

        self.setLayout(layout)
        print("布局设置完成")  # 调试信息

    def accept(self):
        super().accept()

    def get_credentials(self):
        return self.username_edit.text().strip(), self.email_edit.text().strip(), self.password_edit.text().strip()


class HistoryDialog(QDialog):
    def __init__(self, access_token, parent=None):
        super().__init__(parent)
        self.access_token = access_token
        self.setWindowTitle("历史记录")
        self.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout()

        # 控制栏
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("每页显示:"))
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["5", "10", "20", "50"])
        self.limit_combo.setCurrentText("10")
        control_layout.addWidget(self.limit_combo)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_history)
        control_layout.addWidget(self.refresh_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "描述", "操作", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # 分页
        pagination_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("第 1 页")
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)

        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        self.setLayout(layout)

        self.current_page = 0
        self.total_count = 0
        self.load_history()

    def load_history(self):
        try:
            limit = int(self.limit_combo.currentText())
            skip = self.current_page * limit
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"http://localhost:8000/user/history?skip={skip}&limit={limit}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                self.total_count = data["total_count"]
                self.display_history(data["records"])
                self.update_pagination()
            elif response.status_code == 401:
                QMessageBox.critical(self, "错误", "认证失败")
                self.reject()
            else:
                QMessageBox.critical(self, "错误", f"获取历史记录失败: {response.status_code}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "错误", "无法连接到后端服务器")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")

    def display_history(self, records):
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            # 时间
            created_at = record["created_at"].split("T")[0] + " " + record["created_at"].split("T")[1][:8]
            self.table.setItem(row, 0, QTableWidgetItem(created_at))
            # 描述
            desc = record["description"][:50] + "..." if len(record["description"]) > 50 else record["description"]
            self.table.setItem(row, 1, QTableWidgetItem(desc))
            # 操作按钮
            view_btn = QPushButton("查看")
            view_btn.clicked.connect(lambda checked, r=record: self.view_record(r))
            self.table.setCellWidget(row, 2, view_btn)
            # 详情
            self.table.setItem(row, 3, QTableWidgetItem(f"Session: {record['session_id']}"))

    def view_record(self, record):
        """查看记录详情"""
        dialog = RecordDetailDialog(record, self)
        dialog.exec()

    def update_pagination(self):
        limit = int(self.limit_combo.currentText())
        total_pages = (self.total_count + limit - 1) // limit
        current_page_display = self.current_page + 1
        self.page_label.setText(f"第 {current_page_display} 页 / 共 {total_pages} 页")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(current_page_display < total_pages)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_history()

    def next_page(self):
        limit = int(self.limit_combo.currentText())
        if (self.current_page + 1) * limit < self.total_count:
            self.current_page += 1
            self.load_history()


class RecordDetailDialog(QDialog):
    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("记录详情")
        self.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout()

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"描述: {record['description']}"))
        info_layout.addWidget(QLabel(f"Session ID: {record['session_id']}"))
        created_at = record["created_at"].split("T")[0] + " " + record["created_at"].split("T")[1][:8]
        info_layout.addWidget(QLabel(f"创建时间: {created_at}"))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 内容标签页
        tab_widget = QTabWidget()

        # Schema
        schema_tab = QWidget()
        schema_layout = QVBoxLayout()
        schema_text = QTextEdit()
        schema_text.setPlainText(json.dumps(record["schema_result"], indent=2, ensure_ascii=False))
        schema_text.setReadOnly(True)
        schema_layout.addWidget(schema_text)
        schema_tab.setLayout(schema_layout)
        tab_widget.addTab(schema_tab, "Schema")

        # ER模型
        if record.get("er_model_result"):
            er_tab = QWidget()
            er_layout = QVBoxLayout()
            er_text = QTextEdit()
            er_text.setPlainText(json.dumps(record["er_model_result"], indent=2, ensure_ascii=False))
            er_text.setReadOnly(True)
            er_layout.addWidget(er_text)
            er_tab.setLayout(er_layout)
            tab_widget.addTab(er_tab, "ER模型")

        # DDL
        ddl_tab = QWidget()
        ddl_layout = QVBoxLayout()
        ddl_text = QTextEdit()
        ddl_text.setPlainText(record["ddl_result"])
        ddl_text.setReadOnly(True)
        ddl_layout.addWidget(ddl_text)
        ddl_tab.setLayout(ddl_layout)
        tab_widget.addTab(ddl_tab, "DDL")

        layout.addWidget(tab_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)


class ModifyEntitiesDialog(QDialog):
    def __init__(self, schema, session_id, access_token, parent=None):
        super().__init__(parent)
        self.schema = schema.copy()
        self.session_id = session_id
        self.access_token = access_token
        self.setWindowTitle("修改实体和关系")
        self.setGeometry(200, 200, 800, 600)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # 标签页
        tab_widget = QTabWidget()

        # 实体管理标签页
        entity_tab = QWidget()
        entity_layout = QVBoxLayout()

        # 实体列表
        entity_list_group = QGroupBox("实体列表")
        entity_list_layout = QVBoxLayout()
        self.entity_list = QListWidget()
        self.load_entities()
        entity_list_layout.addWidget(self.entity_list)

        # 实体操作按钮
        entity_btn_layout = QHBoxLayout()
        modify_entity_btn = QPushButton("修改实体")
        modify_entity_btn.clicked.connect(self.modify_entity)
        entity_btn_layout.addWidget(modify_entity_btn)

        add_entity_btn = QPushButton("添加实体")
        add_entity_btn.clicked.connect(self.add_entity)
        entity_btn_layout.addWidget(add_entity_btn)

        delete_entity_btn = QPushButton("删除实体")
        delete_entity_btn.clicked.connect(self.delete_entity)
        entity_btn_layout.addWidget(delete_entity_btn)

        entity_list_layout.addLayout(entity_btn_layout)
        entity_list_group.setLayout(entity_list_layout)
        entity_layout.addWidget(entity_list_group)

        entity_tab.setLayout(entity_layout)
        tab_widget.addTab(entity_tab, "实体管理")

        # 关系管理标签页
        relation_tab = QWidget()
        relation_layout = QVBoxLayout()

        # 关系列表
        relation_list_group = QGroupBox("关系列表")
        relation_list_layout = QVBoxLayout()
        self.relation_list = QListWidget()
        self.load_relations()
        relation_list_layout.addWidget(self.relation_list)

        # 关系操作按钮
        relation_btn_layout = QHBoxLayout()
        modify_relation_btn = QPushButton("修改关系")
        modify_relation_btn.clicked.connect(self.modify_relation)
        relation_btn_layout.addWidget(modify_relation_btn)

        add_relation_btn = QPushButton("添加关系")
        add_relation_btn.clicked.connect(self.add_relation)
        relation_btn_layout.addWidget(add_relation_btn)

        delete_relation_btn = QPushButton("删除关系")
        delete_relation_btn.clicked.connect(self.delete_relation)
        relation_btn_layout.addWidget(delete_relation_btn)

        relation_list_layout.addLayout(relation_btn_layout)
        relation_list_group.setLayout(relation_list_layout)
        relation_layout.addWidget(relation_list_group)

        relation_tab.setLayout(relation_layout)
        tab_widget.addTab(relation_tab, "关系管理")

        layout.addWidget(tab_widget)

        # 确定/取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def load_entities(self):
        """加载实体列表"""
        self.entity_list.clear()
        for entity in self.schema["entities"]:
            attrs_text = ", ".join([f"{attr['name']}({attr['data_type']})" for attr in entity["attributes"]])
            item_text = f"{entity['table_name']}: {attrs_text}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entity)
            self.entity_list.addItem(item)

    def load_relations(self):
        """加载关系列表"""
        self.relation_list.clear()
        for relation in self.schema["relationships"]:
            item_text = f"{relation['from_table']}.{relation['from_column']} -> {relation['to_table']}.{relation['to_column']} ({relation['on_delete']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, relation)
            self.relation_list.addItem(item)

    def modify_entity(self):
        """修改实体"""
        current_item = self.entity_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择要修改的实体")
            return

        entity = current_item.data(Qt.ItemDataRole.UserRole)
        dialog = ModifyEntityDialog(entity, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            modified_entity = dialog.get_entity()
            # 调用API修改实体
            self.call_modify_entity_api(modified_entity)

    def add_entity(self):
        """添加实体"""
        dialog = AddEntityDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_entity = dialog.get_entity()
            # 调用API添加实体
            self.call_add_entity_api(new_entity)

    def delete_entity(self):
        """删除实体"""
        current_item = self.entity_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择要删除的实体")
            return

        entity = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "确认删除",
                                   f"确定要删除实体 '{entity['table_name']}' 吗？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # 调用API删除实体
            self.call_delete_entity_api(entity["table_name"])

    def modify_relation(self):
        """修改关系"""
        current_item = self.relation_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择要修改的关系")
            return

        relation = current_item.data(Qt.ItemDataRole.UserRole)
        dialog = ModifyRelationDialog(relation, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            old_relation, new_relation = dialog.get_relations()
            # 调用API修改关系
            self.call_modify_relation_api(old_relation, new_relation)

    def add_relation(self):
        """添加关系"""
        dialog = AddRelationDialog(self.schema["entities"], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_relation = dialog.get_relation()
            # 调用API添加关系
            self.call_add_relation_api(new_relation)

    def delete_relation(self):
        """删除关系"""
        current_item = self.relation_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择要删除的关系")
            return

        relation = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "确认删除",
                                   f"确定要删除关系 '{relation['from_table']}.{relation['from_column']} -> {relation['to_table']}.{relation['to_column']}' 吗？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # 调用API删除关系
            self.call_delete_relation_api(relation)

    def call_modify_entity_api(self, entity):
        """调用修改实体API"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "session_id": self.session_id,
                "entity_name": entity["table_name"],
                "new_attributes": entity["attributes"],
                "new_table_name": entity.get("new_table_name")
            }
            response = requests.put("http://localhost:8000/modify-entity", json=payload, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", "实体修改成功")
                self.refresh_schema()
            else:
                QMessageBox.critical(self, "错误", f"修改失败: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"网络错误: {str(e)}")

    def call_add_entity_api(self, entity):
        """调用添加实体API"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "session_id": self.session_id,
                "entity": entity
            }
            response = requests.post("http://localhost:8000/add-entity", json=payload, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", "实体添加成功")
                self.refresh_schema()
            else:
                QMessageBox.critical(self, "错误", f"添加失败: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"网络错误: {str(e)}")

    def call_delete_entity_api(self, entity_name):
        """调用删除实体API"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "session_id": self.session_id,
                "entity_name": entity_name
            }
            response = requests.request("DELETE", "http://localhost:8000/delete-entity", json=payload, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", "实体删除成功")
                self.refresh_schema()
            else:
                QMessageBox.critical(self, "错误", f"删除失败: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"网络错误: {str(e)}")

    def call_modify_relation_api(self, old_relation, new_relation):
        """调用修改关系API"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "session_id": self.session_id,
                "old_relationship": old_relation,
                "new_relationship": new_relation
            }
            response = requests.put("http://localhost:8000/modify-relationship", json=payload, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", "关系修改成功")
                self.refresh_schema()
            else:
                QMessageBox.critical(self, "错误", f"修改失败: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"网络错误: {str(e)}")

    def call_add_relation_api(self, relation):
        """调用添加关系API"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "session_id": self.session_id,
                "relationship": relation
            }
            response = requests.post("http://localhost:8000/add-relationship", json=payload, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", "关系添加成功")
                self.refresh_schema()
            else:
                QMessageBox.critical(self, "错误", f"添加失败: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"网络错误: {str(e)}")

    def call_delete_relation_api(self, relation):
        """调用删除关系API"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "session_id": self.session_id,
                "relationship": relation
            }
            response = requests.request("DELETE", "http://localhost:8000/delete-relationship", json=payload, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", "关系删除成功")
                self.refresh_schema()
            else:
                QMessageBox.critical(self, "错误", f"删除失败: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"网络错误: {str(e)}")

    def refresh_schema(self):
        """刷新schema数据"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"http://localhost:8000/user/history?skip=0&limit=1", headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data["records"]:
                    record = data["records"][0]
                    self.schema = record["schema_result"]
                    self.load_entities()
                    self.load_relations()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"刷新失败: {str(e)}")


class ModifyEntityDialog(QDialog):
    def __init__(self, entity, parent=None):
        super().__init__(parent)
        self.entity = entity.copy()
        self.setWindowTitle("修改实体")
        self.setGeometry(300, 300, 500, 400)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # 表名
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("表名:"))
        self.name_edit = QLineEdit(self.entity["table_name"])
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 属性列表
        attr_group = QGroupBox("属性")
        attr_layout = QVBoxLayout()
        self.attr_list = QListWidget()
        self.load_attributes()
        attr_layout.addWidget(self.attr_list)

        attr_btn_layout = QHBoxLayout()
        add_attr_btn = QPushButton("添加属性")
        add_attr_btn.clicked.connect(self.add_attribute)
        attr_btn_layout.addWidget(add_attr_btn)

        remove_attr_btn = QPushButton("删除属性")
        remove_attr_btn.clicked.connect(self.remove_attribute)
        attr_btn_layout.addWidget(remove_attr_btn)

        attr_layout.addLayout(attr_btn_layout)
        attr_group.setLayout(attr_layout)
        layout.addWidget(attr_group)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def load_attributes(self):
        self.attr_list.clear()
        for attr in self.entity["attributes"]:
            item_text = f"{attr['name']} ({attr['data_type']}) {'[PK]' if attr['is_primary_key'] else ''}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, attr)
            self.attr_list.addItem(item)

    def add_attribute(self):
        dialog = AddAttributeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            attr = dialog.get_attribute()
            self.entity["attributes"].append(attr)
            self.load_attributes()

    def remove_attribute(self):
        current_item = self.attr_list.currentItem()
        if current_item:
            attr = current_item.data(Qt.ItemDataRole.UserRole)
            self.entity["attributes"].remove(attr)
            self.load_attributes()

    def get_entity(self):
        self.entity["table_name"] = self.name_edit.text().strip()
        return self.entity


class AddEntityDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加实体")
        self.setGeometry(300, 300, 400, 300)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # 表名
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("表名:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 属性
        self.attributes = []

        attr_group = QGroupBox("属性")
        attr_layout = QVBoxLayout()
        self.attr_list = QListWidget()
        attr_layout.addWidget(self.attr_list)

        add_attr_btn = QPushButton("添加属性")
        add_attr_btn.clicked.connect(self.add_attribute)
        attr_layout.addWidget(add_attr_btn)

        attr_group.setLayout(attr_layout)
        layout.addWidget(attr_group)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def add_attribute(self):
        dialog = AddAttributeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            attr = dialog.get_attribute()
            self.attributes.append(attr)
            self.update_attr_list()

    def update_attr_list(self):
        self.attr_list.clear()
        for attr in self.attributes:
            item_text = f"{attr['name']} ({attr['data_type']}) {'[PK]' if attr['is_primary_key'] else ''}"
            self.attr_list.addItem(item_text)

    def get_entity(self):
        return {
            "table_name": self.name_edit.text().strip(),
            "attributes": self.attributes
        }


class AddAttributeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加属性")
        self.setGeometry(300, 300, 300, 200)
        self.initUI()

    def initUI(self):
        layout = QFormLayout()

        self.name_edit = QLineEdit()
        layout.addRow("属性名:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["INT", "VARCHAR(255)", "TEXT", "DATETIME", "DECIMAL(10,2)", "BOOLEAN"])
        layout.addRow("数据类型:", self.type_combo)

        self.pk_check = QCheckBox("是否为主键")
        layout.addRow(self.pk_check)

        self.comment_edit = QLineEdit()
        layout.addRow("注释:", self.comment_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_attribute(self):
        return {
            "name": self.name_edit.text().strip(),
            "data_type": self.type_combo.currentText(),
            "is_primary_key": self.pk_check.isChecked(),
            "comment": self.comment_edit.text().strip()
        }


class ModifyRelationDialog(QDialog):
    def __init__(self, relation, parent=None):
        super().__init__(parent)
        self.old_relation = relation.copy()
        self.new_relation = relation.copy()
        self.setWindowTitle("修改关系")
        self.setGeometry(300, 300, 400, 200)
        self.initUI()

    def initUI(self):
        layout = QFormLayout()

        self.from_table_edit = QLineEdit(self.new_relation["from_table"])
        layout.addRow("源表:", self.from_table_edit)

        self.from_column_edit = QLineEdit(self.new_relation["from_column"])
        layout.addRow("源列:", self.from_column_edit)

        self.to_table_edit = QLineEdit(self.new_relation["to_table"])
        layout.addRow("目标表:", self.to_table_edit)

        self.to_column_edit = QLineEdit(self.new_relation["to_column"])
        layout.addRow("目标列:", self.to_column_edit)

        self.on_delete_combo = QComboBox()
        self.on_delete_combo.addItems(["CASCADE", "SET NULL", "RESTRICT"])
        self.on_delete_combo.setCurrentText(self.new_relation["on_delete"])
        layout.addRow("删除行为:", self.on_delete_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def accept(self):
        self.new_relation = {
            "from_table": self.from_table_edit.text().strip(),
            "from_column": self.from_column_edit.text().strip(),
            "to_table": self.to_table_edit.text().strip(),
            "to_column": self.to_column_edit.text().strip(),
            "on_delete": self.on_delete_combo.currentText()
        }
        super().accept()

    def get_relations(self):
        return self.old_relation, self.new_relation


class AddRelationDialog(QDialog):
    def __init__(self, entities, parent=None):
        super().__init__(parent)
        self.entities = entities
        self.setWindowTitle("添加关系")
        self.setGeometry(300, 300, 400, 200)
        self.initUI()

    def initUI(self):
        layout = QFormLayout()

        self.from_table_combo = QComboBox()
        self.from_table_combo.addItems([e["table_name"] for e in self.entities])
        layout.addRow("源表:", self.from_table_combo)

        self.from_column_edit = QLineEdit()
        layout.addRow("源列:", self.from_column_edit)

        self.to_table_combo = QComboBox()
        self.to_table_combo.addItems([e["table_name"] for e in self.entities])
        layout.addRow("目标表:", self.to_table_combo)

        self.to_column_edit = QLineEdit()
        layout.addRow("目标列:", self.to_column_edit)

        self.on_delete_combo = QComboBox()
        self.on_delete_combo.addItems(["CASCADE", "SET NULL", "RESTRICT"])
        self.on_delete_combo.setCurrentText("CASCADE")
        layout.addRow("删除行为:", self.on_delete_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_relation(self):
        return {
            "from_table": self.from_table_combo.currentText(),
            "from_column": self.from_column_edit.text().strip(),
            "to_table": self.to_table_combo.currentText(),
            "to_column": self.to_column_edit.text().strip(),
            "on_delete": self.on_delete_combo.currentText()
        }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SchemaGeneratorGUI()
    gui.show()
    sys.exit(app.exec())