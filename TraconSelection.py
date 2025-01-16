import sys
import requests
import math
import json
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
from collections import deque

import os


class SplashScreen(QSplashScreen):
    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        splash_image_path = os.path.join(base_dir, "Resources", "pics", "splash-screen.png")
        pixmap = QPixmap(splash_image_path)
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

    def main():
        app = QApplication(sys.argv)

        # Create and show the splash screen
        splash = SplashScreen()
        splash.show()

        # Set a timer to close the splash screen after 10 seconds and show the main dialog
        QTimer.singleShot(10000, splash.close)
        QTimer.singleShot(10000, lambda: TraconSelectionDialog(app))

        sys.exit(app.exec_())

    if __name__ == "__main__":
        main()


class TraconSelectionDialog(QDialog):
    def __init__(self, tracon_names, parent=None):

        super().__init__(parent)
        self.setWindowTitle("Select TRACON")

        # Set the window size and make it center-aligned
        self.setFixedSize(1000, 800)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)  # No borders
        self.pixmap = QPixmap('C:/Users/abbym/Documents/RadarView/Resources/pics/launch-background.png')

        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "Resources", "pics", "launch-background.png")
        self.pixmap = QPixmap(image_path)


        # Main layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)  # Center the entire layout

        # Centered container for the selection box
        container = QWidget(self)
        container.setStyleSheet("background-color: rgba(61, 61, 61, 0.8); border-radius: 10px; padding: 20px;")
        container_layout = QVBoxLayout(container)

        # Label with sleek modern style
        self.label = QLabel("Select a TRACON to load:", container)
        container_layout.addWidget(self.label)

        self.label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #E1E1E1;
            margin-bottom: 20px;
            text-align: center;
        """)

        # ComboBox for TRACON names
        self.comboBox = QComboBox(container)
        self.comboBox.addItems(tracon_names)
        container_layout.addWidget(self.comboBox)

        # Style the comboBox with smooth edges and modern font
        self.comboBox.setStyleSheet("""
            QComboBox {
                background-color: #4C4C4C;
                font-size: 16px;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #888;
                color: #E1E1E1;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: #E1E1E1;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #555;
            }
        """)

        # Create buttons layout
        button_layout = QHBoxLayout()
        container_layout.addLayout(button_layout)

        # OK Button
        self.ok_button = QPushButton("OK", container)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color:rgb(0, 0, 0);
                color: white;
                font-size: 16px;
                padding: 12px 30px;
                border-radius: 8px;
                border: none;

            }
            QPushButton:hover {
                background-color:rgb(255, 255, 255);
                color: black;

            }
        """)

        # Cancel Button
        self.cancel_button = QPushButton("Cancel", container)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color:rgb(134, 134, 134);
                color: white;
                font-size: 16px;
                padding: 12px 30px;
                border-radius: 8px;
                border: none;
            }
        """)

        layout.addWidget(container)  # Add the container with all elements to the main layout

    def get_selected_tracon(self):
        """Return the selected TRACON name."""
        return self.comboBox.currentText()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)  # Draw the background image
        super().paintEvent(event)




