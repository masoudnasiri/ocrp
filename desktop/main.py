import sys
import requests
import asyncio
import websockets
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QTextEdit,
    QGridLayout,
    QLineEdit,  # Import QLineEdit for adding camera
    QMessageBox, # Import QMessageBox for showing error messages
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import cv2
import numpy as np
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Backend URLs (make sure these are correct)
REST_API_URL = "http://127.0.0.1:5001"
WEBSOCKET_URL = "ws://127.0.0.1:5000"


class APIClient:
    """
    Handles communication with the backend REST API.
    """

    @staticmethod
    def get_cameras():
        try:
            response = requests.get(f"{REST_API_URL}/cameras")
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching cameras: {e}")
            return []  # Return an empty list in case of an error

    @staticmethod
    def add_camera(ip, location):
        """Adds a new camera to the backend."""
        data = {"ip_address": ip, "location": location}
        try:
            response = requests.post(f"{REST_API_URL}/cameras", json=data)
            response.raise_for_status()
            return True  # Indicate success
        except requests.exceptions.RequestException as e:
            logging.error(f"Error adding camera: {e}")
            return False  # Indicate failure

    @staticmethod
    def get_ocr_results():
        try:
            response = requests.get(f"{REST_API_URL}/ocr/results")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching OCR results: {e}")
            return []


class CameraStreamThread(QThread):
    """
    Thread for receiving and displaying the camera stream via WebSocket.
    """

    frame_received = pyqtSignal(np.ndarray)

    def __init__(self, camera_id):
        super().__init__()
        self.camera_id = camera_id
        self.running = True

    async def receive_stream(self):
        """
        Connects to the WebSocket server and receives frames.
        """
        uri = f"{WEBSOCKET_URL}/stream/{self.camera_id}"  # Corrected URL
        logging.info(f"Connecting to WebSocket: {uri}")
        try:
            async with websockets.connect(uri) as websocket:
                while self.running:
                    frame_data = await websocket.recv()
                    np_arr = np.frombuffer(frame_data, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is not None and not frame.size == 0:
                        self.frame_received.emit(frame)
                    else:
                        logging.warning("Received empty or invalid frame")
        except websockets.exceptions.ConnectionClosedError as e:
            logging.error(f"WebSocket connection closed unexpectedly: {e}")
        except websockets.exceptions.InvalidURI as e:
            logging.error(f"Invalid WebSocket URI: {e}")
        except Exception as e:
            logging.error(f"Error receiving stream: {e}")

    def run(self):
        """Starts the asyncio event loop to handle the WebSocket connection."""

        asyncio.run(self.receive_stream())

    def stop(self):
        """Stops the thread."""
        self.running = False
        self.quit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Container OCR Desktop App")
        self.setGeometry(100, 100, 800, 700)  # Increased height to accommodate input fields
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()

        # Camera List Display
        self.camera_list_label = QLabel("Cameras:")
        self.camera_list = QTextEdit()
        self.refresh_cameras_button = QPushButton("Refresh Cameras")
        self.refresh_cameras_button.clicked.connect(self.load_cameras)

        self.layout.addWidget(self.camera_list_label)
        self.layout.addWidget(self.camera_list)
        self.layout.addWidget(self.refresh_cameras_button)

        # Add Camera Input Fields
        self.add_camera_label = QLabel("Add Camera:")
        self.ip_address_input = QLineEdit()
        self.ip_address_input.setPlaceholderText("IP Address")
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Location")
        self.add_camera_button = QPushButton("Add")
        self.add_camera_button.clicked.connect(self.add_new_camera)

        self.layout.addWidget(self.add_camera_label)
        self.layout.addWidget(self.ip_address_input)
        self.layout.addWidget(self.location_input)
        self.layout.addWidget(self.add_camera_button)

        # Stream Display
        self.start_stream_button = QPushButton("Start Stream (Camera ID 1)")
        self.start_stream_button.clicked.connect(self.start_stream)
        self.stream_label = QLabel("Camera Stream")
        self.stream_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the stream label

        self.layout.addWidget(self.start_stream_button)
        self.layout.addWidget(self.stream_label)

        self.central_widget.setLayout(self.layout)
        self.load_cameras()  # Load cameras on startup
        self.stream_thread = None # Initialize stream_thread

    def load_cameras(self):
        """Fetches and displays the list of cameras from the backend."""
        cameras = APIClient.get_cameras()
        self.camera_list.setText(json.dumps(cameras, indent=2))

    def add_new_camera(self):
        """Adds a new camera using the provided IP address and location."""

        ip_address = self.ip_address_input.text()
        location = self.location_input.text()

        if not ip_address or not location:
            QMessageBox.warning(self, "Input Required", "Please enter both IP Address and Location.")
            return

        if APIClient.add_camera(ip_address, location):
            QMessageBox.information(self, "Camera Added", "Camera added successfully.")
            self.load_cameras()  # Refresh the camera list
            self.ip_address_input.clear()
            self.location_input.clear()
        else:
            QMessageBox.critical(self, "Error", "Failed to add camera.")

    def start_stream(self):
        """Starts the camera stream in a separate thread."""

        if self.stream_thread is not None and self.stream_thread.isRunning():
            QMessageBox.warning(self, "Stream Running", "A stream is already running.")
            return

        self.stream_thread = CameraStreamThread(camera_id=1)  # Hardcoded camera_id = 1
        self.stream_thread.frame_received.connect(self.update_frame)
        self.stream_thread.start()
        logging.info("Stream started")

    def update_frame(self, frame):
        """Updates the displayed frame in the UI."""

        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        qimg = QPixmap.fromImage(
            QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        )
        self.stream_label.setPixmap(
            qimg.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
        )

    def closeEvent(self, event):
        """Handles window closing event to stop the stream thread."""

        if self.stream_thread is not None and self.stream_thread.isRunning():
            self.stream_thread.stop()
            self.stream_thread.wait()  # Wait for the thread to finish
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec())