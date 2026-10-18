import { useEffect, useRef, useState } from "react";
import { actions, pickPath, useApp, type Plot } from "../store";
import { fmtNum, useT } from "../i18n";

/** T15: a plot in video mode - a local video played with the timeline.
 *  data time = video time + offset. LOCKED (normal): the cursor moves the video (drag the
 *  timeline, jump to an event, timeline playback plays it at the same speed) and the video's own
 *  controls move the cursor. LINING UP: "Line up…" unlocks them, so the video and the cursor can
 *  each be put on the same moment; "Lock here" sets the offset from the two and locks again.
 *  Seeks this view makes itself are remembered, so they do not come back as "the user seeked". */
export default function VideoView({ plot }: { plot: Plot }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const el = useRef<HTMLVideoElement>(null);
  const v = plot.video;
  const offset = v?.offset ?? 0;
  const t1 = useApp((s) => (s.cursor.on ? s.cursor.t1 : null));
  const playing = useApp((s) => s.playing);
  const speed = useApp((s) => s.playSpeed);
  const [dur, setDur] = useState<number | null>(null);
  const [err, setErr] = useState(false);
  const offsetRef = useRef(offset);
  offsetRef.current = offset;
  const driving = useRef(false);        // the video's own controls are playing it: the cursor follows
  const [locked, setLocked] = useState(true);
  const lockedRef = useRef(true);
  lockedRef.current = locked;
  const ownSeek = useRef<number | null>(null);

  const target = t1 === null ? null : t1 - offset;
  const outside = target !== null && dur !== null && (target < 0 || target > dur);

  const seek = (to: number) => {
    const e = el.current;
    if (!e) return;
    ownSeek.current = to;
    e.currentTime = to;
  };

  // the cursor moves the video
  useEffect(() => {
    const e = el.current;
    if (!e || !locked || target === null || driving.current || dur === null) return;
    const want = Math.min(Math.max(target, 0), dur);
    if (Math.abs(e.currentTime - want) > (playing ? 0.3 : 0.04)) seek(want);
  }, [target, playing, dur, locked]);

  // timeline playback plays the video (up to the speed a browser plays; faster: it follows by seeking)
  useEffect(() => {
    const e = el.current;
    if (!e || driving.current || !locked) return;
    if (playing && !outside && speed <= 16) {
      e.playbackRate = speed;
      e.play().catch(() => { /* not allowed / not loaded: it still follows by seeking */ });
    } else e.pause();
  }, [playing, speed, outside, locked]);

  // the video's own controls move the cursor
  useEffect(() => {
    const e = el.current;
    if (!e) return;
    let raf = 0;
    const tick = () => {
      if (!driving.current) return;
      actions.setTime(e.currentTime + offsetRef.current);
      raf = requestAnimationFrame(tick);
    };
    const onPlay = () => {
      if (useApp.getState().playing || !lockedRef.current) return;   // timeline playback started it / lining up
      driving.current = true;
      raf = requestAnimationFrame(tick);
    };
    const onPause = () => {
      if (!driving.current) return;
      driving.current = false;
      cancelAnimationFrame(raf);
      actions.setTime(e.currentTime + offsetRef.current);
    };
    const onSeeked = () => {
      const mine = ownSeek.current !== null && Math.abs(e.currentTime - ownSeek.current) < 0.05;
      ownSeek.current = null;
      if (!mine && lockedRef.current && !useApp.getState().playing) actions.setTime(e.currentTime + offsetRef.current);
    };
    e.addEventListener("play", onPlay);
    e.addEventListener("pause", onPause);
    e.addEventListener("ended", onPause);
    e.addEventListener("seeked", onSeeked);
    return () => {
      cancelAnimationFrame(raf);
      e.removeEventListener("play", onPlay);
      e.removeEventListener("pause", onPause);
      e.removeEventListener("ended", onPause);
      e.removeEventListener("seeked", onSeeked);
    };
  }, [v?.path]);

  const choose = async () => {
    const path = await pickPath({ mode: "open", title: t("videoPickTitle"), exts: [".mp4", ".m4v", ".webm", ".mov", ".ogv", ".mkv"] });
    if (path) { setErr(false); setDur(null); actions.setVideo(plot.id, path); }
  };
  const sync = () => {
    const e = el.current;
    const st = useApp.getState();
    if (!e || !st.cursor.on || st.cursor.t1 === null) {
      st.toast({ kind: "error", text: t("videoNeedsCursor") });
      return;
    }
    const off = st.cursor.t1 - e.currentTime;
    e.pause();
    actions.setVideoOffset(plot.id, off);
    setLocked(true);
    st.toast({ kind: "info", text: t("videoSynced", { s: fmtNum(Math.round(off * 1000) / 1000, lang, 6) }) });
  };

  const name = v ? v.path.split(/[\\/]/).pop() ?? v.path : "";
  return (
    <div className="video-view">
      <div className="video-bar">
        {v && <span className="video-name" title={v.path}>{name}</span>}
        <button className="btn sm" onClick={choose}>{v ? t("videoChange") : t("videoChoose")}</button>
        {v && <>
          {locked
            ? <button className="btn sm video-sync" onClick={() => { el.current?.pause(); setLocked(false); }} title={t("videoUnlockHint")}>{t("videoUnlock")}</button>
            : <button className="btn sm video-sync on" onClick={sync} title={t("videoSyncHint")}>{t("videoSync")}</button>}
          <label className="video-off" title={t("videoOffsetHint")}>{t("videoOffset")}
            <input key={offset} type="number" step="0.01" defaultValue={offset} aria-label={t("videoOffset")}
              onBlur={(e) => actions.setVideoOffset(plot.id, parseFloat(e.target.value))}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} /> s
          </label>
        </>}
      </div>
      {v && !locked && <div className="video-lining">{t("videoLiningUp")}</div>}
      {!v && <div className="plot-empty">{t("videoNeedsFile")}</div>}
      {v && !err && (
        <div className="video-stage">
          <video ref={el} src={`/api/video?path=${encodeURIComponent(v.path)}`} controls preload="auto" muted playsInline
            onLoadedMetadata={(e) => setDur(Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : null)}
            onError={() => setErr(true)} />
          {outside && <div className="video-outside">{t("videoOutside")}</div>}
        </div>
      )}
      {v && err && <div className="plot-empty">{t("videoFailed", { name })}</div>}
    </div>
  );
}
