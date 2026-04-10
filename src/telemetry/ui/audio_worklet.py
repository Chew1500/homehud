"""AudioWorklet processor JS for capturing PCM audio in the browser.

Captures float32 samples from the browser's audio context, downsamples
to 16 kHz, converts to int16, and posts buffers to the main thread.
"""

AUDIO_PROCESSOR_JS = """\
class AudioCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._recording = false;
    this._sourceSampleRate = sampleRate; // browser's native rate
    this._targetRate = 16000;

    this.port.onmessage = (e) => {
      if (e.data.command === 'start') {
        this._buffer = [];
        this._recording = true;
      } else if (e.data.command === 'stop') {
        this._recording = false;
        // Downsample and convert accumulated buffer
        const float32 = new Float32Array(this._buffer);
        const resampled = this._downsample(float32, this._sourceSampleRate, this._targetRate);
        const int16 = this._floatToInt16(resampled);
        this.port.postMessage({ type: 'audio', samples: int16.buffer }, [int16.buffer]);
        this._buffer = [];
      }
    };
  }

  process(inputs, outputs, parameters) {
    if (!this._recording) return true;
    const input = inputs[0];
    if (input.length > 0) {
      const channelData = input[0]; // mono — first channel
      for (let i = 0; i < channelData.length; i++) {
        this._buffer.push(channelData[i]);
      }
      // Send RMS level for visualisation (~every 128 samples = ~2.9ms)
      let sum = 0;
      for (let i = 0; i < channelData.length; i++) {
        sum += channelData[i] * channelData[i];
      }
      const rms = Math.sqrt(sum / channelData.length);
      this.port.postMessage({ type: 'level', rms: rms });
    }
    return true;
  }

  _downsample(float32, fromRate, toRate) {
    if (fromRate === toRate) return float32;
    const ratio = fromRate / toRate;
    const newLength = Math.floor(float32.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const srcIndex = i * ratio;
      const lower = Math.floor(srcIndex);
      const upper = Math.min(lower + 1, float32.length - 1);
      const frac = srcIndex - lower;
      result[i] = float32[lower] * (1 - frac) + float32[upper] * frac;
    }
    return result;
  }

  _floatToInt16(float32) {
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16;
  }
}

registerProcessor('audio-capture-processor', AudioCaptureProcessor);
"""
