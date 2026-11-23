
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    this.bufferSize = 2048;
    this.hopSize = 1024;

    this.buffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.totalSamples = 0;
  }

  process(inputs, outputs) {
    const input = inputs[0];
    const output = outputs[0];

    // Output silence to prevent microphone feedback
    if (output) {
      for (const channel of output) {
        channel.fill(0);
      }
    }

    if (!input || input.length === 0) {
      return true;
    }

    const channel = input[0];

    for (let i = 0; i < channel.length; i++) {
      this.buffer[this.writeIndex] = channel[i];

      this.writeIndex =
        (this.writeIndex + 1) % this.bufferSize;

      this.totalSamples++;

      if (this.totalSamples < this.bufferSize) {
        continue;
      }

      if (
        (this.totalSamples - this.bufferSize) %
        this.hopSize !== 0
      ) {
        continue;
      }

      const frame = new Float32Array(this.bufferSize);

      for (let j = 0; j < this.bufferSize; j++) {
        const index =
          (this.writeIndex + j) % this.bufferSize;

        frame[j] = this.buffer[index];
      }

      this.port.postMessage(frame, [frame.buffer]);
    }

    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
