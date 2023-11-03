import typer
from rich.progress import track 
import requests
import json
import re
import os
from datetime import datetime
import time

from reportlab.lib.pagesizes import letter, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

domain = "ninemanga.com"
subdomain = "www"
data_path = ".data"

def createFolder(path):
    if not os.path.exists(path):
        os.mkdir(path)

def getUriContent(url):
    try:
        r = requests.get(url)
        if(r.status_code == 200):
            return r
        
        print('Error Response. Sleeping 30 seconds. and retrying '+url+'.')
        time.sleep(30)
        return getUriContent(url)
    except Exception as e:
        print('Sleeping 5 seconds. and retrying '+url+'.')
        print(e)
        time.sleep(5)
        return getUriContent(url)

def getEndpointPageContent(endpoint):
    url = f"https://{subdomain}.{domain}{endpoint}"
    response = getUriContent(url)
    content = response.content.decode('utf-8')
    return content.replace('\n', '')

def removeDomain(url):
    return url.replace(f"https://{subdomain}.{domain}", '')

def search(str):
    endpoint = f"/search/ajax/?term={str}"
    content = getEndpointPageContent(endpoint)
    return json.loads(content)

def select(list):
    typer.secho(f"Results:", fg=typer.colors.YELLOW, bg=typer.colors.BLACK)
    for i in range(len(list)):
        print(f"  [{i+1}] {list[i][1]}")
    manga_selection = int(typer.prompt("Type the number to select the manga"))
    selection = list[manga_selection-1]
    return {"name": selection[1], "endpoint": selection[2], "last_chapter": selection[3], "author": selection[4], "picture": selection[0], "chapters": []}

def getChapterInfo(content):
    results = re.findall(r'<a class="chapter_list_a" href="(.+?)" title="(.+?)">(.+?)</a>', content)
    name = results[0][2]
    endpoint = removeDomain(results[0][0])
    results = re.findall(r'<span>(.+?)</span>', content)
    date = results[0]
    return {"name": name, "endpoint": endpoint, "date": date, "pages": []}

# def getChapterPagesList(content):
#     links = re.findall(r'<a href="(.+?)" target="_blank">1</a><a href="(.+?)" target="_blank">3</a><a shref="(.+?)" target="_blank">6</a><a href="(.+?)" target="_blank">10</a>', content)
#     print(links)
#     if(len(links) == 0):
#         links = re.findall(r'<a href="(.+?)" target="_blank">1</a><a href="(.+?)" target="_blank">3</a><a shref="(.+?)" target="_blank">6</a>', content)
#     if(len(links) == 0):
#         links = re.findall(r'<a href="(.+?)" target="_blank">1</a><a href="(.+?)" target="_blank">3</a>', content)
#     if(len(links) == 0):
#         links = re.findall(r'<a href="(.+?)" target="_blank">1</a>', content)

#     return links[len(links)-1]

# def getChapterName(content):
#     results = re.findall(r'<a class="chapter_list_a" href="(.+?)" title="(.+?)">(.+?)</a>', content)
#     return results[0][2]

def getChaptersList(manga):
    content = getEndpointPageContent(f"/manga/{manga["endpoint"]}.html")
    list_content = re.findall(r'<ul class="sub_vol_ul" id="(.+?)">(.+?)</ul>', content) 
    print(f"{manga["name"]} has {len(list_content)} lists")
    chapters = []
    for i in range(len(list_content)):
        items = re.findall(r'<li>(.+?)</li>', list_content[i][1]) 
        for j in range(len(items)):
            chapter_info = getChapterInfo(items[j])
            chapters.append(chapter_info)
    print(f"{manga["name"]} has {len(chapters)} chapter")
    chapters.reverse()
    return chapters

def getChaptersContent(chapters):
    for i in track(range(len(chapters)), description="Listing Chapters..."):
        print(f"   [{i+1}/{len(chapters)}] Listing {chapters[i]['name']} chapter content")
        pages = getChapterContent(chapters[i])
        chapters[i]["pages"] = pages
    return chapters

def getChapterContent(chapter):
    content = getEndpointPageContent(chapter['endpoint'])
    select_pages = re.findall(r'<select name="page" id="page" (.+?)>(.+?)</select>', content) 
    pages_content = select_pages[0][1]
    pages_content = pages_content.replace(' selected', '')
    pages = re.findall(r'<option value="(.+?)">(.+?)</option>', pages_content) 
    chapter_pages = []
    for i in range(len(pages)):
        page = {"endpoint":pages[i][0], "number": pages[i][1]}
        chapter_pages.append(page)
    return chapter_pages

def getMangaPath(manga):
    createFolder(data_path)
    manga_path = f"{data_path}/{manga["name"]}"
    createFolder(manga_path)
    return manga_path

def writeMangaDataFile(path, manga):
    with open(f"{path}/data.json", 'w') as fp:
        json.dump(manga, fp)

def numberWithPrefixes(number, total):
    return str(number).rjust(len(str(total)), '0')

def writePDF(image_folder):
    # Get list of images in the folder
    images = [f for f in os.listdir(image_folder) if f.endswith('.jpg') or f.endswith('.png') or f.endswith('.webp')]

    # Create a new canvas object
    c = canvas.Canvas(f"{image_folder}.pdf")

    for image_file in images:
        # Open image file
        img = Image.open(os.path.join(image_folder, image_file))
        # Get image dimensions
        width, height = img.size

        # Set page size to image size
        c.setPageSize((width, height))

        # Draw image on canvas at full size
        c.drawImage(os.path.join(image_folder, image_file), 0, 0, width=width, height=height)

        # Move to next page
        c.showPage()

    # Save PDF file
    c.save()

def downloadManga(manga):
    for i in range(len(manga["chapters"])):
        manga_path = getMangaPath(manga)
        folder_path = f"{manga_path}/{numberWithPrefixes(i+1, len(manga["chapters"]))} - {manga["chapters"][i]["name"]}"
        createFolder(folder_path)
        typer.secho(f"Downloading Chapter: {manga["chapters"][i]["name"]}", fg=typer.colors.GREEN, bg=typer.colors.BLACK)
        for j in track(range(len(manga["chapters"][i]["pages"]))):
            content = getEndpointPageContent(manga["chapters"][i]["pages"][j]["endpoint"])
            page_url = re.findall(r'<img class="manga_pic manga_pic_1" id="manga_pic_1" i="1" e="1" src="(.+?)" border="0" />', content)
            image_response = getUriContent(page_url[0])
            fp = open(f"{folder_path}/{numberWithPrefixes(j, len(manga["chapters"][i]["pages"]))}.webp", 'wb')
            fp.write(image_response.content)
            fp.close()
        writePDF(folder_path)

        
def main():
    typer.secho(f"Nine Manga Crawler!", fg=typer.colors.WHITE, bg=typer.colors.BLUE)
    manga_name = typer.prompt("Enter manga name to search")
    typer.secho(f"Searching: {manga_name}", fg=typer.colors.YELLOW, bg=typer.colors.BLACK)
    results = search(manga_name)
    if(len(results) > 0):
        manga = select(results)
        manga_path = getMangaPath(manga)
        chapters = getChaptersList(manga)
        chapters = getChaptersContent(chapters)
        manga["chapters"] = chapters
        manga["last_update"] = str(datetime.now())
        writeMangaDataFile(manga_path, manga)
        downloadManga(manga)
        typer.secho(f"Download Finished!", fg=typer.colors.WHITE, bg=typer.colors.GREEN)
    else :
        typer.secho(f"No results for: {manga_name}", fg=typer.colors.RED, bg=typer.colors.BLACK)

if __name__ == "__main__":
    typer.run(main)