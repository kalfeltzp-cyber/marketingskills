#!/usr/bin/env python3
"""Assemble the /niche edit from generated shot clips with ffmpeg.

Usage:
  python3 assemble.py --clips DIR --out final.mp4 [--timeline timeline.json]
                      [--bpm 126] [--audio song.mp3 --audio-start 0.0]

DIR must contain S1.mp4 ... S17.mp4 (any of .mp4/.mov/.webm).
--bpm snaps every cut to that song's beat grid (keeps order, min 1 beat per shot).
--audio muxes the song (starting at --audio-start seconds of the song, which should
be the downbeat) and fades it out over the last 0.4 s. Without --audio the output is
silent, ready for the song to be added in TikTok/CapCut.
Prints a JSON summary (shots, durations, total) on success.
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TL = os.path.join(HERE, "..", "references", "timeline.json")
EXTS = (".mp4", ".mov", ".webm", ".mkv")


def die(msg):
    print(json.dumps({"status": "FAIL", "error": msg}))
    sys.exit(1)


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        die(f"cannot read duration of {path}")


def find_clip(d, sid):
    for e in EXTS:
        p = os.path.join(d, sid + e)
        if os.path.isfile(p):
            return p
    return None


def snap(shots, bpm):
    beat = 60.0 / bpm
    t, prev = [], 0
    for s in shots:
        b = max(prev + 1, round(s["out"] / beat))
        t.append(b)
        prev = b
    out, start = [], 0
    for s, b in zip(shots, t):
        out.append(dict(s, **{"in": start * beat, "out": b * beat}))
        start = b
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeline", default=DEFAULT_TL)
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--audio")
    ap.add_argument("--audio-start", type=float, default=0.0)
    a = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not installed")
    tl = json.load(open(a.timeline))
    W, H, FPS = tl["width"], tl["height"], tl["fps"]
    shots = snap(tl["shots"], a.bpm) if a.bpm else tl["shots"]

    inputs, filters, summary = [], [], []
    for i, s in enumerate(shots):
        p = find_clip(a.clips, s["id"])
        if not p:
            die(f"missing clip {s['id']} in {a.clips}")
        dur = round(s["out"] - s["in"], 3)
        src = probe_duration(p)
        # take the most active middle portion; pad by freezing last frame if too short
        ss = max(0.0, (src - dur) / 2) if src > dur else 0.0
        pad = max(0.0, dur - src + 0.05)
        inputs += ["-ss", f"{ss:.3f}", "-i", p]
        f = (f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
             f"fps={FPS},setsar=1")
        if pad > 0:
            f += f",tpad=stop_mode=clone:stop_duration={pad:.3f}"
        if s.get("bw"):
            f += ",hue=s=0,eq=contrast=1.15:brightness=-0.02,noise=alls=14:allf=t,vignette=PI/5"
        f += f",trim=duration={dur},setpts=PTS-STARTPTS,format=yuv420p[v{i}]"
        filters.append(f)
        summary.append({"id": s["id"], "dur": dur, "src": round(src, 2), "bw": bool(s.get("bw"))})

    total = round(sum(x["dur"] for x in summary), 3)
    filters.append("".join(f"[v{i}]" for i in range(len(shots))) +
                   f"concat=n={len(shots)}:v=1:a=0[vout]")
    cmd = ["ffmpeg", "-v", "error", "-y"] + inputs
    maps = ["-map", "[vout]"]
    if a.audio:
        if not os.path.isfile(a.audio):
            die(f"audio not found: {a.audio}")
        cmd += ["-ss", f"{a.audio_start:.3f}", "-i", a.audio]
        ai = len(shots)
        filters.append(f"[{ai}:a]atrim=duration={total},asetpts=PTS-STARTPTS,"
                       f"afade=t=out:st={max(0, total - 0.4):.3f}:d=0.4[aout]")
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-filter_complex", ";".join(filters)] + maps + [
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-t", f"{total}", "-movflags", "+faststart", a.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(r.stderr.strip()[-2000:])
    got = probe_duration(a.out)
    if abs(got - total) > 0.1:
        die(f"output duration {got:.2f}s != expected {total:.2f}s")
    print(json.dumps({"status": "PASS", "out": a.out, "total": total,
                      "bpm": a.bpm, "shots": summary}, indent=1))


if __name__ == "__main__":
    main()
