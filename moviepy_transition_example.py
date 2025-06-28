from moviepy import VideoFileClip, concatenate_videoclips

# Load your video clips
clip1 = VideoFileClip("video1.mp4")
clip2 = VideoFileClip("video2.mp4")
clip3 = VideoFileClip("video3.mp4")

# Concatenate with crossfade transition (duration in seconds)
final_clip = concatenate_videoclips(
    [clip1, clip2, clip3],
    method="compose",
    transition=lambda c: c.crossfadein(1),  # 1 second crossfade
)

# Write the result to a file
final_clip.write_videofile("output_with_transition.mp4", codec="libx264")
