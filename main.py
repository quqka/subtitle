import sys, importlib,os, time, wave, tempfile, threading
from PyQt5.QtWidgets import QApplication, QStyle, QWidget, QVBoxLayout, QHBoxLayout, QLabel,QPushButton, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt,QThread, pyqtSignal

import rtoml
import pyaudiowpatch as pyaudio
import pvleopard
#import torch
#from faster_whisper import WhisperModel as whisper

config_data = rtoml.load(open("config.toml"))
translator = importlib.import_module(config_data['translator']['api'])
#os.environ['KMP_DUPLICATE_LIB_OK']='True'
#model_size = "medium"
#model_path = "./medium"

leopard = pvleopard.create(access_key=config_data['att']['key'])

class RetimeServer(QThread):

    data = pyqtSignal(str)
    AUDIO_BUFFER = 5
    def __init__(self):
        super(RetimeWhisperServer,self).__init__()

    def record_audio(self, p, device):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            filename = f.name
            wave_file = wave.open(filename, "wb")
            wave_file.setnchannels(device["maxInputChannels"])
            wave_file.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
            wave_file.setframerate(int(device["defaultSampleRate"]))

            def callback(in_data, frame_count, time_info, status):
                wave_file.writeframes(in_data)
                return (in_data, pyaudio.paContinue)

            stream = p.open(
                format=pyaudio.paInt16,
                channels=device["maxInputChannels"],
                rate=int(device["defaultSampleRate"]),
                frames_per_buffer=pyaudio.get_sample_size(pyaudio.paInt16),
                input=True,
                input_device_index=device["index"],
                stream_callback=callback,
            )

            try:
                time.sleep(self.AUDIO_BUFFER)
            finally:
                stream.stop_stream()
                stream.close()
                wave_file.close()
        return filename

    def audio_to_text(self, filename, model):
        #segments, info = model.transcribe(filename, beam_size=5, language="zh", vad_filter=True, vad_parameters=dict(min_silence_duration_ms=1000))
        try:
            transcript, words = leopard.process_file(filename)
            os.remove(filename)
            text = ""
            for word in words:
                text += f" {word.word}"
            translate_text = translator.translate(config_data['translator']['appid'], config_data['translator']['appkey'], )
            if translate_text:
                self.data.emit(translate_text)
        except:pass
        #for segment in segments:
        #    self.data.emit(segment.text)
        #    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))

    def run(self):
        #print("Loading model...")
        #device = "cuda" if torch.cuda.is_available() else "cpu"
        #print(f"Using {device} device.")
        model = None
        # model = whisper("medium", device=device, compute_type="float32")
        # model = whisper(model_size_or_path=model_path, device=device, local_files_only=True, compute_type="int8")
        print("Model loaded.")

        with pyaudio.PyAudio() as pya:
            try:
                # Get default WASAPI info
                wasapi_info = pya.get_host_api_info_by_type(pyaudio.paWASAPI)
            except OSError:
                sys.exit()

            default_speakers = pya.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )

            if not default_speakers["isLoopbackDevice"]:
                for loopback in pya.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        default_speakers = loopback
                        break
                else:
                    sys.exit()

            while True:
                filename = self.record_audio(pya, default_speakers)
                thread = threading.Thread(target=self.audio_to_text, args=(filename, model))
                thread.start()


class TransparentWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.server = RetimeServer()
        self.initUI()
        self.server.start()
        self.server.data.connect(lambda text: self.captionLabel.setText(text))
        

    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.set_center()
        self.setWindowTitle('Windows')
        self.setObjectName("mainWindow")

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        headerLayout = QHBoxLayout()
        # headerLayout.setAlignment(Qt.AlignRight | Qt.AlignTop)
        spacer = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        headerLayout.addItem(spacer)
        self.headerWidget = QWidget()
        self.headerWidget.setObjectName("headerWidget")
        self.headerWidget.setStyleSheet("background-color: rgba(100, 100, 100, 0);")
        self.headerWidget.setLayout(headerLayout)

        miniButton = QPushButton()
        miniButton.setObjectName("miniButton")
        miniButton.setStyleSheet("border :1px solid black;max-height: 20px;max-width: 20px;")
        miniButton.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
        miniButton.clicked.connect(self.showMinimized)
        headerLayout.addWidget(miniButton)
        
        exitButton = QPushButton()
        exitButton.setObjectName("exitButton")
        exitButton.setStyleSheet("border :1px solid black;max-height: 20px;max-width: 20px;")
        exitButton.clicked.connect(self.close)
        exitButton.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        headerLayout.addWidget(exitButton)

        self.contentWidget = QWidget()
        self.contentWidget.setObjectName("contentWidget")
        self.contentWidget.setStyleSheet("background-color: rgba(134, 134, 134, 0);")
        contentLayout = QHBoxLayout()
        contentLayout.setContentsMargins(0, 0, 0, 0)
        self.captionLabel = QLabel("Hello")
        self.captionLabel.setAlignment(Qt.AlignCenter)
        self.captionLabel.setStyleSheet("color: black;font-size: 20px;")
        self.captionLabel.setObjectName("captionLabel")
        self.contentWidget.setLayout(contentLayout)
        contentLayout.addWidget(self.captionLabel)

        layout.addWidget(self.headerWidget, 1)
        layout.addWidget(self.contentWidget, 3)
        self.setLayout(layout)
    
    def set_center(self):
        desktop = QApplication.desktop()
        self.resize(int(desktop.width() / 1.5), 120)
        size = self.geometry()
        newLeft = (desktop.width() - size.width()) / 2
        newTop = desktop.height() - (size.height() * 2)
        self.move(int(newLeft),int(newTop))
    
    def mousePressEvent(self,evt):
        self.mouse_x = evt.globalX()
        self.mouse_y = evt.globalY()
        self.origin_x = self.x()
        self.origin_y = self.y()

    def mouseMoveEvent(self,evt):
        move_x = evt.globalX() - self.mouse_x
        move_y = evt.globalY() - self.mouse_y
        dest_x = self.origin_x + move_x
        dest_y = self.origin_y + move_y
        self.move(dest_x,dest_y)

    def enterEvent (self, event):
        self.contentWidget.setStyleSheet("background-color: rgba(134, 134, 134, 0.85);")
        self.headerWidget.setStyleSheet("background-color: rgba(100, 100, 100, 0.85);")
        
    def leaveEvent (self, event):
        self.contentWidget.setStyleSheet("background-color: rgba(134, 134, 134, 0);")
        self.headerWidget.setStyleSheet("background-color: rgba(100, 100, 100, 0);")
        

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TransparentWindow()
    window.show()
    sys.exit(app.exec_())
