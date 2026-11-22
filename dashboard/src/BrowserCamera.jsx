import { useEffect, useRef, useState } from "react";
import styles from "./OpsPages.module.css";
import playerStyles from "./Analyze.module.css";

export function BrowserCamera() {
  const [url, setUrl] = useState("");
  const [input, setInput] = useState(null);
  const [status, setStatus] = useState("Disconnected");
  const [message, setMessage] = useState("");
  const player = useRef(null);
  const webcam = useRef(null);
  const request = useRef(0);

  const disconnect = () => {
    request.current += 1;
    webcam.current?.getTracks().forEach(track => track.stop());
    webcam.current = null;
    setInput(null);
    setStatus("Disconnected");
    setMessage("");
  };
  useEffect(() => () => {
    request.current += 1;
    webcam.current?.getTracks().forEach(track => track.stop());
  }, []);

  useEffect(() => {
    if (input?.stream) player.current.srcObject = input.stream;
  }, [input]);
  useEffect(() => {
    if (status !== "Connecting" || !input?.url) return undefined;
    const timeout = setTimeout(() => {
      setInput(null);
      setStatus("Error");
      setMessage("The stream did not send playable video. Check the stream address and format.");
    }, 15000);
    return () => clearTimeout(timeout);
  }, [input, status]);

  const fail = text => {
    disconnect();
    setStatus("Error");
    setMessage(text);
  };

  const connectStream = event => {
    event.preventDefault();
    let streamUrl;
    try {
      streamUrl = new URL(url.trim());
    } catch {
      fail("Enter a complete HTTPS video stream address.");
      return;
    }
    if (streamUrl.protocol !== "https:" || streamUrl.username || streamUrl.password) {
      fail("Browser preview requires an HTTPS video stream without credentials.");
      return;
    }
    disconnect();
    setStatus("Connecting");
    setInput({ url: streamUrl.href, id: request.current });
  };

  const connectWebcam = async () => {
    disconnect();
    if (!navigator.mediaDevices?.getUserMedia) {
      fail("Webcam access is unavailable in this browser window. Check your browser camera permissions.");
      return;
    }
    setStatus("Connecting");
    setMessage("Allow camera access when your browser asks.");
    const current = request.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (request.current !== current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      webcam.current = stream;
      stream.getVideoTracks().forEach(track => track.addEventListener("ended", () => {
        if (request.current === current) fail("The webcam stopped sending video.");
      }, { once: true }));
      setInput({ stream, id: current });
    } catch (error) {
      if (request.current !== current) return;
      fail(error.name === "NotAllowedError" ? "Camera permission was denied. Allow camera access in your browser and try again."
        : "A webcam could not be opened. Check that a camera is available and try again.");
    }
  };

  const active = status === "Connecting" || status === "Connected";
  return <section className={styles.card} aria-label="Browser camera preview">
    <h3>Real Live Camera / Server</h3>
    <p role="status" className={styles.text}>{status === "Disconnected" ? "No live camera connected" : status}</p>
    <form className={styles.cameraForm} onSubmit={connectStream}>
      <label>HTTPS video stream
        <input type="text" inputMode="url" placeholder="https://camera.example/stream" value={url} onChange={e => setUrl(e.target.value)} />
      </label>
      <div className={styles.actions}>
        <button type="submit" className={styles.button} disabled={!url.trim()}>Connect stream</button>
        <button type="button" className={styles.button} onClick={connectWebcam}>Use webcam</button>
        <button type="button" className={styles.button} onClick={disconnect} disabled={!active}>Disconnect</button>
      </div>
    </form>
    {message && <p role="status" className={styles.text}>{message}</p>}
    {input && <video key={input.id} className={playerStyles.browserCamera} ref={player} src={input.url} muted autoPlay playsInline controls
      aria-label="Camera preview" onPlaying={() => { setStatus("Connected"); setMessage(""); }}
      onWaiting={() => setStatus("Connecting")}
      onError={() => fail("The browser could not play this stream. Check the address and video format.")}
      onEnded={disconnect} />}
    <p className={styles.muted}>This page previews webcams and browser-compatible HTTPS video. AI processing is unavailable in preview mode.</p>
  </section>;
}
