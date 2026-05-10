from ddgs import DDGS
with DDGS() as ddgs:
    results = list(ddgs.text("UAE Iran news", max_results=3))
    print(results)
