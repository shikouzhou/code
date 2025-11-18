import sys
import json
import requests
import mysql.connector
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox, QSplitter, QGroupBox, QDialog, QFormLayout,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox
)
from PyQt6.QtCore import Qt

class SchemaGeneratorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.current_schema = None
        self.current_ddl = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('数据库模式生成器')
        self.setGeometry(100, 100, 1200, 800)

        layout = QVBoxLayout()

        # 输入区域
        input_group = QGroupBox("自然语言描述")
        input_layout = QVBoxLayout()
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入自然语言描述，如：我要做一个校园二手交易平台，有用户、商品、订单，用户可以发布商品，其他人可以下单购买")
        input_layout.addWidget(self.input_text)

        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成模式")
        self.generate_btn.clicked.connect(self.generate_schema)
        button_layout.addWidget(self.generate_btn)

        self.edit_btn = QPushButton("编辑模式")
        self.edit_btn.clicked.connect(self.edit_schema)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)

        input_layout.addLayout(button_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

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

        layout.addWidget(splitter)
        self.setLayout(layout)

    def generate_schema(self):
        description = self.input_text.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "警告", "请输入自然语言描述")
            return

        try:
            response = requests.post("http://localhost:8000/generate-schema", json={"description": description})
            if response.status_code == 200:
                data = response.json()
                self.current_schema = data["schema"]
                self.current_ddl = data["ddl"]
                self.display_results(data)
                self.edit_btn.setEnabled(True)
                QMessageBox.information(self, "成功", "模式生成成功")
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
            # 连接MySQL，假设本地root用户，无密码，数据库test
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="",
                database="test"
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
            relational_schema = convert_to_relational_schema(er_model)
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SchemaGeneratorGUI()
    gui.show()
    sys.exit(app.exec())