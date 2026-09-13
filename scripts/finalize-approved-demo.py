"""Splice an actual verified Ambiguous save into the final 20 seconds; local media only."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "artifacts/video"
evidence = json.loads((ROOT / "docs/evidence/approved-save.json").read_text())
assert evidence["verified_readback"] and evidence["exact_content_compared"]
assert evidence["exports"] and all(item["verified"] for item in evidence["exports"])
saved_at = float(evidence["saved_at_seconds"])
assert 0 <= saved_at <= 18, "Save proof must appear within the captured clip before finalizing."

def timestamp(seconds):
    milliseconds = round(seconds * 1000)
    return f"{milliseconds//3600000:02}:{milliseconds//60000%60:02}:{milliseconds//1000%60:02},{milliseconds%1000:03}"

raw = VIDEO / "approved-save-raw"
raw.mkdir(exist_ok=True)
caption = raw / "approved-save.srt"
caption.write_text(f"1\n00:00:00,000 --> {timestamp(saved_at)}\nApprove the exact brief and $219.97 shopping list.\n\n2\n{timestamp(saved_at)} --> 00:00:20,000\nSaved to Ambiguous. Document content verified by read-back.\n")
style = "FontName=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00302923,BorderStyle=3,Outline=1,Shadow=0,MarginV=20,Alignment=2"
filters = f"[0:v]trim=duration=100,setpts=PTS-STARTPTS,fps=30[a];[1:v]trim=duration=20,setpts=PTS-STARTPTS,fps=30,subtitles=artifacts/video/approved-save-raw/approved-save.srt:force_style='{style}'[b];[a][b]concat=n=2:v=1:a=0,format=yuv420p[out]"
target = raw / "showroom-demo-final.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(VIDEO/"showroom-demo.mp4"), "-i", str(VIDEO/"approved-save.mp4"), "-filter_complex", filters, "-map", "[out]", "-t", "120", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(target)], cwd=ROOT, check=True)
subprocess.run(["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"], check=True)
target.replace(VIDEO / "showroom-demo.mp4")
srt = VIDEO / "showroom-demo.srt"
entries = srt.read_text().strip().split("\n\n")[:6]
entries[-1] = entries[-1].replace("00:01:42,000", "00:01:40,000")
entries += [f"7\n00:01:40,000 --> {timestamp(100+saved_at)}\nApprove the exact brief and $219.97 shopping list.", f"8\n{timestamp(100+saved_at)} --> 00:02:00,000\nSaved to Ambiguous. Document content verified by read-back."]
srt.write_text("\n\n".join(entries) + "\n")
print("Final 120-second reel includes the actual approved save and verified read-back.")
