import re

pattern = re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/reel/([A-Za-z0-9_-]+)")
url = "https://www.instagram.com/reel/DXZdc0giKPV/?igsh=MXEzcHIyYzJ4dXFqNQ=="

match = pattern.search(url)
if match:
    print(f"ID: {match.group(1)}")
else:
    print("No match")
