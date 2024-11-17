import sys
import hashlib
import getpass
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QPushButton, QInputDialog, QMessageBox, QMenu, 
    QDialog, QScrollArea, QShortcut, QApplication, QLineEdit, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QByteArray, QTimer, QEvent, QBuffer
from PyQt5.QtGui import QKeySequence, QImage, QPixmap, QIcon
import sqlite3
import pyperclip
from datetime import datetime, timezone
import base64
from PIL import Image
import io
import logging
import threading
import time
import os
from PyQt5.QtCore import QSettings

logging.basicConfig(level=logging.DEBUG)

def adapt_datetime(dt):
    """Convert datetime to UTC ISO format string."""
    return dt.astimezone(timezone.utc).isoformat()

def convert_datetime(val):
    """Convert ISO format string to datetime object."""
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        return None

def hash_password(password):
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

class HoverPreviewWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create preview label
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)
        
        # Style the window
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)
        
    def showPreview(self, content, content_type, pos):
        if content_type == 'image':
            try:
                # Convert base64 to image
                image_data = QByteArray.fromBase64(content.encode())
                image = QImage.fromData(image_data)
                
                if not image.isNull():
                    # Calculate preview size (max 300x300)
                    preview_size = 300
                    scaled_pixmap = QPixmap.fromImage(image).scaled(
                        preview_size, preview_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.preview_label.setPixmap(scaled_pixmap)
                    
                    # Adjust window size to content
                    self.adjustSize()
                    
                    # Position window near cursor but not under it
                    self.move(pos.x() + 20, pos.y() - self.height() // 2)
                    self.show()
            except Exception as e:
                logging.error(f"Error showing preview: {e}")
        elif content_type == 'text':
            # For text, show first 100 characters
            preview_text = content[:100] + ('...' if len(content) > 100 else '')
            self.preview_label.setText(preview_text)
            self.preview_label.setStyleSheet("QLabel { background-color: white; padding: 5px; }")
            
            # Adjust window size to content
            self.adjustSize()
            
            # Position window near cursor
            self.move(pos.x() + 20, pos.y() - self.height() // 2)
            self.show()

class PreviewDialog(QDialog):
    def __init__(self, content, content_type, timestamp=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Quick Look')
        
        # Get screen size for better initial sizing
        screen = QApplication.primaryScreen().geometry()
        default_width = min(1024, screen.width() * 0.7)
        default_height = min(768, screen.height() * 0.7)
        self.setGeometry(100, 100, int(default_width), int(default_height))
        
        # Add Cmd+W shortcut to close only preview
        self.close_shortcut = QShortcut(QKeySequence.Close, self)
        self.close_shortcut.activated.connect(self.close)
        self.close_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)  # Add spacing between widgets

        # Add timestamp if available
        if timestamp:
            try:
                # Convert UTC timestamp to local time
                utc_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                local_dt = utc_dt.astimezone()
                timestamp_str = local_dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")
                
                timestamp_label = QLabel(f"Created: {timestamp_str}")
                timestamp_label.setAlignment(Qt.AlignCenter)
                timestamp_label.setStyleSheet("""
                    QLabel {
                        color: #666666;
                        padding: 5px;
                        border-bottom: 1px solid #eee;
                        font-size: 12px;
                    }
                """)
                main_layout.addWidget(timestamp_label)
            except ValueError as e:
                logging.error(f"Error parsing timestamp: {e}")
        
        if content_type == 'text':
            scroll = QScrollArea()
            text_widget = QLabel(content)
            text_widget.setWordWrap(True)
            text_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            
            # Set proper font for text
            font = text_widget.font()
            font.setPointSize(12)
            text_widget.setFont(font)
            
            # Style the text widget
            text_widget.setStyleSheet("""
                QLabel {
                    background-color: white;
                    padding: 20px;
                    border: 1px solid #eee;
                    border-radius: 5px;
                }
            """)
            
            scroll.setWidget(text_widget)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; }")
            main_layout.addWidget(scroll)
        else:  # image
            image_data = QByteArray.fromBase64(content.encode())
            image = QImage.fromData(image_data)
            
            if not image.isNull():
                # Create info label with dimensions
                info_label = QLabel(f"Original Dimensions: {image.width()}x{image.height()} pixels")
                info_label.setAlignment(Qt.AlignCenter)
                info_label.setStyleSheet("""
                    QLabel {
                        color: #666666;
                        padding: 5px;
                        font-size: 12px;
                    }
                """)
                main_layout.addWidget(info_label)
                
                # Create scroll area with dark background
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                scroll.setStyleSheet("""
                    QScrollArea {
                        background-color: #2d2d2d;
                        border: none;
                    }
                    QScrollBar {
                        background-color: #2d2d2d;
                    }
                    QScrollBar:handle {
                        background-color: #666666;
                    }
                """)
                
                # Create image container with dark background
                container = QWidget()
                container.setStyleSheet("background-color: #2d2d2d;")
                container_layout = QVBoxLayout(container)
                container_layout.setContentsMargins(20, 20, 20, 20)
                
                # Create image label
                image_label = QLabel()
                image_label.setAlignment(Qt.AlignCenter)
                
                # Calculate initial size while preserving aspect ratio
                available_width = self.width() - 80  # Increased margins
                available_height = self.height() - 120  # Increased margins
                
                # Create pixmap and store original
                pixmap = QPixmap.fromImage(image)
                self.original_pixmap = pixmap
                
                # Scale image to fit window while maintaining quality
                if pixmap.width() > available_width or pixmap.height() > available_height:
                    scaled_pixmap = pixmap.scaled(
                        available_width,
                        available_height,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                else:
                    # If image is smaller than window, show at original size
                    scaled_pixmap = pixmap
                
                image_label.setPixmap(scaled_pixmap)
                container_layout.addWidget(image_label, alignment=Qt.AlignCenter)
                
                # Store references for resize events
                self.image_label = image_label
                self.container = container
                
                scroll.setWidget(container)
                main_layout.addWidget(scroll)
            else:
                error_label = QLabel("Error loading image")
                main_layout.addWidget(error_label)
        
        self.setLayout(main_layout)
        
        # Style the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
        """)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Clipboard Manager - Login')
        self.setFixedWidth(300)
        layout = QVBoxLayout()
        
        # Username
        username_layout = QVBoxLayout()
        username_label = QLabel('Username:')
        self.username = QLineEdit()
        self.username.setPlaceholderText('Enter username')
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username)
        layout.addLayout(username_layout)
        
        # Password
        password_layout = QVBoxLayout()
        password_label = QLabel('Password:')
        self.password = QLineEdit()
        self.password.setPlaceholderText('Enter password')
        self.password.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password)
        layout.addLayout(password_layout)
        
        # Remember me checkbox
        self.remember_me = QCheckBox('Remember me')
        layout.addWidget(self.remember_me)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Login button
        self.login_btn = QPushButton('Login')
        self.login_btn.clicked.connect(self.accept)
        self.login_btn.setDefault(True)
        
        # Register button
        self.register_btn = QPushButton('Register')
        self.register_btn.clicked.connect(self.register)
        
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.register_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 12px;
                color: #2c3e50;
                margin-bottom: 2px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                margin-bottom: 10px;
            }
            QCheckBox {
                color: #2c3e50;
                margin: 5px 0;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                margin: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#register_btn {
                background-color: #2ecc71;
            }
            QPushButton#register_btn:hover {
                background-color: #27ae60;
            }
        """)
        
        # Load remembered username if exists
        self.load_remembered_user()
    
    def load_remembered_user(self):
        settings = QSettings('ClipboardManager', 'UserPreferences')
        remembered_username = settings.value('remembered_username', '')
        if remembered_username:
            self.username.setText(remembered_username)
            self.remember_me.setChecked(True)
    
    def save_remembered_user(self):
        settings = QSettings('ClipboardManager', 'UserPreferences')
        if self.remember_me.isChecked():
            settings.setValue('remembered_username', self.username.text())
        else:
            settings.remove('remembered_username')
    
    def register(self):
        self.done(2)  # Custom return code for registration

class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Clipboard Manager - Register')
        self.setFixedWidth(300)
        layout = QVBoxLayout()
        
        # Username
        username_layout = QVBoxLayout()
        username_label = QLabel('Username:')
        self.username = QLineEdit()
        self.username.setPlaceholderText('Choose a username')
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username)
        layout.addLayout(username_layout)
        
        # Password
        password_layout = QVBoxLayout()
        password_label = QLabel('Password:')
        self.password = QLineEdit()
        self.password.setPlaceholderText('Choose a password')
        self.password.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password)
        layout.addLayout(password_layout)
        
        # Confirm Password
        confirm_layout = QVBoxLayout()
        confirm_label = QLabel('Confirm Password:')
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText('Confirm your password')
        self.confirm_password.setEchoMode(QLineEdit.Password)
        confirm_layout.addWidget(confirm_label)
        confirm_layout.addWidget(self.confirm_password)
        layout.addLayout(confirm_layout)
        
        # Register button
        self.register_btn = QPushButton('Create Account')
        self.register_btn.clicked.connect(self.register)
        self.register_btn.setDefault(True)
        layout.addWidget(self.register_btn)
        
        # Back to login button
        self.back_btn = QPushButton('Back to Login')
        self.back_btn.clicked.connect(self.reject)
        layout.addWidget(self.back_btn)
        
        self.setLayout(layout)
        
        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 12px;
                color: #2c3e50;
                margin-bottom: 2px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                margin-bottom: 10px;
            }
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton[text="Back to Login"] {
                background-color: #95a5a6;
            }
            QPushButton[text="Back to Login"]:hover {
                background-color: #7f8c8d;
            }
        """)
    
    def register(self):
        if not self.username.text() or not self.password.text():
            QMessageBox.warning(self, "Error", "Please fill in all fields!")
            return
        if len(self.username.text()) < 3:
            QMessageBox.warning(self, "Error", "Username must be at least 3 characters!")
            return
        if len(self.password.text()) < 6:
            QMessageBox.warning(self, "Error", "Password must be at least 6 characters!")
            return
        if self.password.text() != self.confirm_password.text():
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return
        self.accept()

class ClipboardThread(QThread):
    clipboard_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.previous_content = None
    
    def run(self):
        clipboard = QApplication.clipboard()
        while self.running:
            try:
                mime_data = clipboard.mimeData()
                if mime_data.hasImage():
                    image = clipboard.image()
                    if image and image != self.previous_content:
                        self.clipboard_changed.emit()
                        self.previous_content = image
                elif mime_data.hasText():
                    text = mime_data.text()
                    if text and text != self.previous_content:
                        self.clipboard_changed.emit()
                        self.previous_content = text
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error in clipboard thread: {e}")
                time.sleep(1)
    
    def stop(self):
        self.running = False

class ClipboardManagerV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Clipboard Manager V2')
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize database with timestamp handling
        self.db_connection = sqlite3.connect(
            'clipboard_manager_v2.db',
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False
        )
        
        self.current_session_id = None
        self.current_user_id = None
        self.current_username = None
        self.clipboard_history = []
        self.db_lock = threading.Lock()
        
        self.initDatabase()
        
        # Show login dialog
        if not self.showLogin():
            sys.exit()
            
        self.initUI()
        self.loadAvailableSessions()
        self.startClipboardMonitor()
        
        # Create hover preview window
        self.hover_preview = HoverPreviewWindow()
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.showHoverPreview)

    def showLogin(self):
        while True:
            dialog = LoginDialog(self)
            result = dialog.exec_()
            
            if result == QDialog.Accepted:
                username = dialog.username.text()
                password = dialog.password.text()
                if self.validateUser(username, hash_password(password)):
                    self.current_username = username
                    dialog.save_remembered_user()
                    self.setWindowTitle(f'Clipboard Manager V2 - {username}')
                    return True
                QMessageBox.warning(self, "Error", "Invalid username or password!")
            elif result == 2:  # Register
                reg_dialog = RegisterDialog(self)
                if reg_dialog.exec_() == QDialog.Accepted:
                    username = reg_dialog.username.text()
                    password = reg_dialog.password.text()
                    if self.registerUser(username, password):
                        QMessageBox.information(self, "Success", "Registration successful! Please login.")
                    else:
                        QMessageBox.warning(self, "Error", "Username already exists!")
            else:
                return False
    
    def validateUser(self, username, password_hash):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?',
                      (username, password_hash))
        result = cursor.fetchone()
        if result:
            self.current_user_id = result[0]
            return True
        return False
    
    def registerUser(self, username, password):
        cursor = self.db_connection.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                         (username, hash_password(password)))
            self.db_connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def initUI(self):
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Create top section with horizontal layout
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        top_layout.setSpacing(20)

        # Left side - Sessions section
        sessions_widget = QWidget()
        sessions_layout = QVBoxLayout(sessions_widget)
        sessions_layout.setSpacing(10)
        
        # Sessions header with styling
        sessions_header = QLabel('Available Sessions')
        sessions_header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px;
            }
        """)
        sessions_layout.addWidget(sessions_header)
        
        # Session list with reduced height
        self.session_list = QListWidget()
        self.session_list.setMaximumHeight(150)  # Limit height
        self.session_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        sessions_layout.addWidget(self.session_list)
        
        # Connect session selection change
        self.session_list.itemSelectionChanged.connect(self.loadSession)
        
        # Add sessions widget to left side of top section
        top_layout.addWidget(sessions_widget, stretch=2)

        # Right side - Session management buttons
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setSpacing(10)
        buttons_layout.setAlignment(Qt.AlignTop)
        
        # Button styles
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2472a4;
            }
        """
        
        # Create styled buttons
        self.new_session_button = QPushButton('New Session')
        self.new_session_button.setStyleSheet(button_style)
        self.new_session_button.clicked.connect(self.createNewSession)
        buttons_layout.addWidget(self.new_session_button)
        
        self.rename_button = QPushButton('Rename Session')
        self.rename_button.setStyleSheet(button_style)
        self.rename_button.clicked.connect(self.renameSession)
        buttons_layout.addWidget(self.rename_button)
        
        self.delete_session_button = QPushButton('Delete Session')
        self.delete_session_button.setStyleSheet(button_style.replace('3498db', 'e74c3c').replace('2980b9', 'c0392b').replace('2472a4', 'a93226'))
        self.delete_session_button.clicked.connect(self.deleteSession)
        buttons_layout.addWidget(self.delete_session_button)
        
        self.set_default_button = QPushButton('Set as Default')
        self.set_default_button.setStyleSheet(button_style)
        self.set_default_button.clicked.connect(self.setDefaultSession)
        buttons_layout.addWidget(self.set_default_button)
        
        # Add buttons widget to right side of top section
        top_layout.addWidget(buttons_widget, stretch=1)
        
        # Add top section to main layout
        main_layout.addWidget(top_section)

        # Clipboard history section
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setSpacing(10)
        
        # History header with styling
        history_header = QLabel('Clipboard History')
        history_header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px;
            }
        """)
        history_layout.addWidget(history_header)
        
        # History display
        self.history_display = QListWidget()
        self.history_display.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        
        # Enable mouse tracking for hover preview
        self.history_display.setMouseTracking(True)
        self.history_display.viewport().installEventFilter(self)
        
        # Connect signals
        self.history_display.itemDoubleClicked.connect(self.previewSelectedItem)
        self.history_display.itemActivated.connect(self.previewSelectedItem)
        self.history_display.keyPressEvent = self.historyKeyPressEvent
        
        history_layout.addWidget(self.history_display)
        
        # History management buttons in horizontal layout
        history_buttons = QHBoxLayout()
        
        self.delete_entry_button = QPushButton('Delete Entry')
        self.delete_entry_button.setStyleSheet(button_style.replace('3498db', 'e74c3c').replace('2980b9', 'c0392b').replace('2472a4', 'a93226'))
        self.delete_entry_button.clicked.connect(self.deleteClipboardEntry)
        history_buttons.addWidget(self.delete_entry_button)
        
        self.clear_history_button = QPushButton('Clear History')
        self.clear_history_button.setStyleSheet(button_style.replace('3498db', 'e74c3c').replace('2980b9', 'c0392b').replace('2472a4', 'a93226'))
        self.clear_history_button.clicked.connect(self.clearClipboardHistory)
        history_buttons.addWidget(self.clear_history_button)
        
        history_buttons.addStretch()
        history_layout.addLayout(history_buttons)
        
        # Add history section to main layout with stretch
        main_layout.addWidget(history_widget, stretch=1)
        
        # Enable context menu
        self.history_display.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_display.customContextMenuRequested.connect(self.showContextMenu)
        
        # Create status bar
        self.statusBar()
        
        # Set initial state
        self.loadAvailableSessions()

    def historyKeyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.previewSelectedItem()
        else:
            # Call the parent class's keyPressEvent for other keys
            QListWidget.keyPressEvent(self.history_display, event)

    def initDatabase(self):
        try:
            cursor = self.db_connection.cursor()
            
            # Check if we need to migrate by looking for the users table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            needs_migration = cursor.fetchone() is None
            
            if needs_migration:
                logging.info("Migrating database to new schema...")
                
                # Drop existing tables if they exist
                cursor.execute("DROP TABLE IF EXISTS clipboard_entries")
                cursor.execute("DROP TABLE IF EXISTS sessions")
                
                # Create users table
                cursor.execute('''
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create sessions table with user_id and default flag
                cursor.execute('''
                    CREATE TABLE sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        is_deleted BOOLEAN DEFAULT 0,
                        is_default BOOLEAN DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE(user_id, name)
                    )
                ''')
                
                # Create clipboard entries table
                cursor.execute('''
                    CREATE TABLE clipboard_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        content_type TEXT NOT NULL,
                        width INTEGER,
                        height INTEGER,
                        timestamp TIMESTAMP NOT NULL,
                        is_deleted BOOLEAN DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES sessions (id)
                    )
                ''')
                
                self.db_connection.commit()
                logging.info("Database migration completed successfully")
            
            logging.debug("Database initialized successfully")
            
        except sqlite3.Error as e:
            logging.error(f"Database initialization error: {e}")
            QMessageBox.critical(self, "Database Error", 
                               "Failed to initialize database. The application may not work correctly.")

    def createNewSession(self):
        new_name, ok = QInputDialog.getText(self, 'New Session', 'Enter session name:')
        if ok and new_name:
            cursor = self.db_connection.cursor()
            try:
                cursor.execute('INSERT INTO sessions (user_id, name) VALUES (?, ?)', (self.current_user_id, new_name))
                self.db_connection.commit()
                self.loadAvailableSessions()
                logging.debug(f"New session '{new_name}' created.")
            except sqlite3.IntegrityError:
                logging.debug(f"Session '{new_name}' already exists.")

    def renameSession(self):
        current_item = self.session_list.currentItem()
        if not current_item:
            logging.debug("No session selected to rename.")
            return
        old_name = current_item.text().replace('★ ', '')
        new_name, ok = QInputDialog.getText(self, 'Rename Session', 'Enter new name:')
        if ok and new_name:
            cursor = self.db_connection.cursor()
            try:
                cursor.execute('UPDATE sessions SET name = ? WHERE name = ? AND user_id = ?', (new_name, old_name, self.current_user_id))
                self.db_connection.commit()
                self.loadAvailableSessions()
                logging.debug(f"Session renamed from {old_name} to {new_name}.")
            except sqlite3.IntegrityError:
                logging.debug(f"Session '{new_name}' already exists.")

    def deleteSession(self):
        current_item = self.session_list.currentItem()
        if current_item is None:
            return
        
        session_name = current_item.text().replace('★ ', '')
        cursor = self.db_connection.cursor()
        
        # Soft delete the session
        cursor.execute('UPDATE sessions SET is_deleted = 1 WHERE name = ? AND user_id = ?', (session_name, self.current_user_id))
        # Soft delete all clipboard entries in this session
        cursor.execute('''
            UPDATE clipboard_entries 
            SET is_deleted = 1 
            WHERE session_id IN (SELECT id FROM sessions WHERE name = ? AND user_id = ?)
        ''', (session_name, self.current_user_id))
        
        self.db_connection.commit()
        self.loadAvailableSessions()
        self.current_session_id = None
        self.clipboard_history.clear()
        self.updateHistoryDisplay()

    def deleteClipboardEntry(self):
        current_item = self.history_display.currentItem()
        if current_item is None:
            return

        row = self.history_display.row(current_item)
        if 0 <= row < len(self.clipboard_history):
            content, _, _, _, _ = self.clipboard_history[row]
            cursor = self.db_connection.cursor()
            cursor.execute('''
                UPDATE clipboard_entries 
                SET is_deleted = 1 
                WHERE content = ? AND session_id = ? 
                AND timestamp = (
                    SELECT timestamp 
                    FROM clipboard_entries 
                    WHERE content = ? 
                    AND session_id = ? 
                    AND is_deleted = 0 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                )
            ''', (content, self.current_session_id, content, self.current_session_id))
            self.db_connection.commit()
            self.loadClipboardHistory()

    def clearClipboardHistory(self):
        if self.current_session_id is None:
            return

        cursor = self.db_connection.cursor()
        cursor.execute('''
            UPDATE clipboard_entries 
            SET is_deleted = 1 
            WHERE session_id = ? AND is_deleted = 0
        ''', (self.current_session_id,))
        self.db_connection.commit()
        self.loadClipboardHistory()

    def loadAvailableSessions(self):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT id, name, is_default 
                FROM sessions 
                WHERE user_id = ? AND is_deleted = 0 
                ORDER BY is_default DESC, name
            ''', (self.current_user_id,))
            
            sessions = cursor.fetchall()
            self.session_list.clear()
            
            for session_id, name, is_default in sessions:
                item = QListWidgetItem(f"{'★ ' if is_default else ''}{name}")
                item.setData(Qt.UserRole, session_id)
                self.session_list.addItem(item)
            
            # Load default session or first available
            default_session = next((s for s in sessions if s[2]), sessions[0] if sessions else None)
            if default_session:
                self.current_session_id = default_session[0]
                self.loadSession()
                
        except sqlite3.Error as e:
            logging.error(f"Error loading sessions: {e}")

    def startClipboardMonitor(self):
        self.clipboard_thread = ClipboardThread(self)
        self.clipboard_thread.clipboard_changed.connect(self.onClipboardChanged)
        self.clipboard_thread.start()

    def onClipboardChanged(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            image = clipboard.image()
            if image and not image.isNull():
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.WriteOnly)
                image.save(buffer, 'PNG')
                image_data = byte_array.toBase64().data().decode()
                self.saveClipboardContent(image_data, 'image', image.width(), image.height())
        
        elif mime_data.hasText():
            text = mime_data.text()
            if text:
                self.saveClipboardContent(text, 'text')

    def saveClipboardContent(self, content, content_type='text', width=None, height=None):
        try:
            if not content:
                return
                
            # For text content, limit size but preserve content
            if content_type == 'text' and len(content) > 1000000:  # 1MB limit for text
                logging.warning(f"Large text content detected: {len(content)} bytes")
                content = content[:1000000] + "\n... (content truncated due to size)"
            
            if self.current_session_id is None:
                logging.warning("No session selected, cannot save clipboard content")
                return

            with self.db_lock:
                cursor = self.db_connection.cursor()
                timestamp = datetime.now(timezone.utc)
                
                cursor.execute('''
                    INSERT INTO clipboard_entries 
                    (session_id, content, content_type, width, height, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.current_session_id, content, content_type, width, height, timestamp))
                
                self.db_connection.commit()
                logging.debug(f"Clipboard entry saved for session {self.current_session_id} at {timestamp}")
            
            # Update UI in the main thread
            self.loadClipboardHistory()
            
        except sqlite3.Error as e:
            logging.error(f"Database error while saving clipboard content: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while saving clipboard content: {e}")

    def loadSession(self):
        current_item = self.session_list.currentItem()
        if current_item is None:
            logging.debug("No session selected.")
            return
        session_id = current_item.data(Qt.UserRole)
        logging.debug(f"Loading session: {session_id}")
        self.current_session_id = session_id
        self.loadClipboardHistory()
        self.setWindowTitle(f'Clipboard Manager - {current_item.text().replace("★ ", "")}')
        logging.debug(f"Loaded session from {session_id}.")

    def loadClipboardHistory(self):
        try:
            if self.current_session_id is None:
                return
                
            with self.db_lock:
                cursor = self.db_connection.cursor()
                cursor.execute('''
                    SELECT id, content, content_type, width, height, timestamp 
                    FROM clipboard_entries 
                    WHERE session_id = ? AND is_deleted = 0 
                    ORDER BY timestamp DESC
                ''', (self.current_session_id,))
                
                entries = cursor.fetchall()
            
            self.history_display.clear()
            for entry_id, content, content_type, width, height, timestamp in entries:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                    
                display_time = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
                if content_type == 'text':
                    display_text = f"{display_time} - {content[:100]}{'...' if len(content) > 100 else ''}"
                else:
                    display_text = f"{display_time} - [Image: {width}x{height}]"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, (entry_id, content, content_type))
                self.history_display.addItem(item)
                
        except sqlite3.Error as e:
            logging.error(f"Database error while loading clipboard history: {e}")
            QMessageBox.warning(self, "Error", "Failed to load clipboard history")

    def updateHistoryDisplay(self):
        self.history_display.clear()
        for content, content_type, width, height, timestamp in self.clipboard_history:
            item = QListWidgetItem()
            if content_type == 'image':
                item.setText(f"[Image] {width}x{height}")
                # Create thumbnail
                image_data = QByteArray.fromBase64(content.encode())
                image = QImage.fromData(image_data)
                pixmap = QPixmap.fromImage(image).scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(pixmap))
            else:
                item.setText(str(content))
            
            item.setToolTip(f"Type: {content_type}\nCopied on: {timestamp}")
            self.history_display.addItem(item)

        # Enable context menu
        self.history_display.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_display.customContextMenuRequested.connect(self.showContextMenu)

    def previewSelectedItem(self):
        current_item = self.history_display.currentItem()
        if current_item is None:
            return
        
        row = self.history_display.row(current_item)
        if 0 <= row < len(self.clipboard_history):
            content, content_type, width, height, timestamp = self.clipboard_history[row]
            dialog = PreviewDialog(content, content_type, timestamp, self)
            dialog.exec_()

    def showContextMenu(self, position):
        item = self.history_display.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        preview_action = menu.addAction("Preview")
        copy_action = menu.addAction("Copy to Clipboard")
        delete_action = menu.addAction("Delete")
        
        # Get the selected action
        action = menu.exec_(self.history_display.mapToGlobal(position))
        
        if action == preview_action:
            self.previewSelectedItem()
        elif action == copy_action:
            self.copySelectedItemToClipboard()
        elif action == delete_action:
            self.deleteClipboardEntry()
        
        # No need to explicitly close the menu - Qt handles this automatically

    def copySelectedItemToClipboard(self):
        current_item = self.history_display.currentItem()
        if current_item is None:
            return
        
        row = self.history_display.row(current_item)
        if 0 <= row < len(self.clipboard_history):
            content, content_type, _, _, _ = self.clipboard_history[row]
            clipboard = QApplication.clipboard()
            if content_type == 'image':
                image_data = QByteArray.fromBase64(content.encode())
                image = QImage.fromData(image_data)
                clipboard.setImage(image)
            else:
                clipboard.setText(content)

    def eventFilter(self, source, event):
        if source is self.history_display.viewport():
            if event.type() == QEvent.MouseMove:
                item = self.history_display.itemAt(event.pos())
                if item and item != getattr(self, 'last_hover_item', None):
                    # Hide previous preview if exists
                    self.hover_preview.hide()
                    self.hover_timer.stop()
                    
                    # Start timer for new item
                    self.hover_timer.start(2000)  # 2 seconds delay
                    # Store current item and position for later use
                    self.hover_item = item
                    self.last_hover_item = item
                    self.hover_pos = self.history_display.viewport().mapToGlobal(event.pos())
                elif not item:
                    # Hide preview and stop timer when mouse leaves item
                    self.hover_preview.hide()
                    self.hover_timer.stop()
                    self.last_hover_item = None
            elif event.type() == QEvent.Leave:
                # Hide preview and stop timer when mouse leaves widget
                self.hover_preview.hide()
                self.hover_timer.stop()
                self.last_hover_item = None
        return super().eventFilter(source, event)

    def showHoverPreview(self):
        try:
            if not hasattr(self, 'hover_item') or not self.hover_item:
                return
                
            row = self.history_display.row(self.hover_item)
            if row < 0 or row >= len(self.clipboard_history):
                return
                
            content, content_type, _, _, _ = self.clipboard_history[row]
            if content and content_type:
                self.hover_preview.showPreview(content, content_type, self.hover_pos)
        except (RuntimeError, AttributeError, IndexError) as e:
            logging.debug(f"Hover preview error: {e}")
            # Safely clear hover state
            self.hover_item = None
            if hasattr(self, 'hover_preview'):
                self.hover_preview.hide()

    def copySelectedToClipboard(self):
        try:
            current_item = self.history_display.currentItem()
            if not current_item:
                return
                
            row = self.history_display.row(current_item)
            if row < 0 or row >= len(self.clipboard_history):
                return
                
            content, content_type, _, _, _ = self.clipboard_history[row]
            clipboard = QApplication.clipboard()
            
            # Temporarily disconnect the clipboard monitor to prevent recursive updates
            if hasattr(self, 'clipboard_thread'):
                self.clipboard_thread.running = False
                self.clipboard_thread.wait()
            
            try:
                if content_type == 'text':
                    clipboard.setText(content)
                elif content_type == 'image':
                    if isinstance(content, str):  # Base64 encoded image
                        image_data = base64.b64decode(content)
                        image = QImage()
                        image.loadFromData(image_data)
                        clipboard.setImage(image)
                    elif isinstance(content, QImage):  # QImage object
                        clipboard.setImage(content)
                    else:
                        logging.error(f"Unsupported image content type: {type(content)}")
                        return
                
                # Update status bar
                self.statusBar().showMessage('Copied to clipboard!', 2000)
                logging.debug(f"Copied {content_type} content to clipboard")
                
            except Exception as e:
                logging.error(f"Error copying to clipboard: {e}")
                self.statusBar().showMessage('Failed to copy to clipboard', 2000)
            
            finally:
                # Restart the clipboard monitor
                if hasattr(self, 'clipboard_thread'):
                    self.clipboard_thread.running = True
                    self.clipboard_thread.start()
                
        except Exception as e:
            logging.error(f"Error in copySelectedToClipboard: {e}")
            self.statusBar().showMessage('Failed to copy to clipboard', 2000)

    def setDefaultSession(self):
        if not self.current_session_id:
            return
            
        try:
            cursor = self.db_connection.cursor()
            # Clear any existing default
            cursor.execute('''
                UPDATE sessions 
                SET is_default = 0 
                WHERE user_id = ?
            ''', (self.current_user_id,))
            
            # Set new default
            cursor.execute('''
                UPDATE sessions 
                SET is_default = 1 
                WHERE id = ? AND user_id = ?
            ''', (self.current_session_id, self.current_user_id))
            
            self.db_connection.commit()
            self.loadAvailableSessions()
            QMessageBox.information(self, "Success", "Default session updated!")
            
        except sqlite3.Error as e:
            logging.error(f"Error setting default session: {e}")
            QMessageBox.warning(self, "Error", "Failed to set default session")

    def keyPressEvent(self, event):
        # Handle Cmd+C (or Ctrl+C) to copy selected item
        if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            self.copySelectedToClipboard()
        else:
            super().keyPressEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClipboardManagerV2()
    window.show()
    sys.exit(app.exec_())
