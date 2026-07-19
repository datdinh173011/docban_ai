import os
import urllib.request
import numpy as np

# We import these inside helper methods to allow optional loading
# if dependencies are not yet installed by the user.
sherpa_onnx = None
sf = None

class SpeechToTextProcessor:
    def __init__(self):
        self.model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models", "zipformer"))
        os.makedirs(self.model_dir, exist_ok=True)
        
        self.encoder_path = os.path.join(self.model_dir, "encoder.int8.onnx")
        self.decoder_path = os.path.join(self.model_dir, "decoder.onnx")
        self.joiner_path = os.path.join(self.model_dir, "joiner.int8.onnx")
        self.tokens_path = os.path.join(self.model_dir, "tokens.txt")
        
        self.is_ready = False
        self.recognizer = None

    def initialize_if_needed(self):
        """Lazy initialization of packages and model files download."""
        global sherpa_onnx, sf
        if self.is_ready:
            return True
            
        try:
            import sherpa_onnx as so
            import soundfile as sfile
            sherpa_onnx = so
            sf = sfile
        except ImportError:
            print("[SpeechToText] Missing dependencies: sherpa-onnx or soundfile. Please install them.")
            return False
            
        # Download files if they do not exist
        try:
            self._ensure_models()
            self._init_recognizer()
            self.is_ready = True
            return True
        except Exception as e:
            print(f"[SpeechToText] Initialization failed: {e}")
            return False

    def _ensure_models(self):
        base_url = "https://huggingface.co/csukuangfj2/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/resolve/main/"
        files = {
            "encoder.int8.onnx": self.encoder_path,
            "decoder.onnx": self.decoder_path,
            "joiner.int8.onnx": self.joiner_path,
            "tokens.txt": self.tokens_path
        }
        for name, path in files.items():
            if not os.path.exists(path):
                url = base_url + name
                print(f"[SpeechToText] Downloading {name} from {url} to {path}...")
                
                # Custom downloader to handle chunk-by-chunk download
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                    data = response.read()
                    out_file.write(data)
                print(f"[SpeechToText] Downloaded {name} successfully.")

    def _init_recognizer(self):
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=self.tokens_path,
            encoder=self.encoder_path,
            decoder=self.decoder_path,
            joiner=self.joiner_path,
            num_threads=1,
            sample_rate=16000,
            feature_dim=80,
            decoding_method="greedy_search"
        )

    def transcribe(self, audio_bytes_or_path) -> str:
        """Transcribe audio data using the local ONNX Zipformer model."""
        if not self.initialize_if_needed():
            raise RuntimeError("SpeechToTextProcessor is not initialized. Please ensure sherpa-onnx and soundfile are installed.")
            
        # Read audio file using soundfile
        data, sample_rate = sf.read(audio_bytes_or_path)
        
        # Convert multi-channel (stereo) to mono if needed
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        data = data.astype(np.float32)
        
        # Create sherpa-onnx stream
        stream = self.recognizer.create_stream()
        
        # Accept waveform and decode
        stream.accept_waveform(sample_rate, data)
        self.recognizer.decode_stream(stream)
        
        result_text = stream.result.text
        return result_text.strip()
