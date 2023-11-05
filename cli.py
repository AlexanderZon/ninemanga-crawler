import typer
from rich.progress import track 
import requests
import json
import re
import os
from datetime import datetime
import time
import html2text

from reportlab.lib.pagesizes import letter, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

data_path = ".data"
data_json_file = "data.json"

config_map = {
    "en": {
        "domain": "ninemanga.com",
        "subdomain": "www",
    },
    "es": {
        "domain": "ninemanga.com",
        "subdomain": "es",
    },
    "pt": {
        "domain": "ninemanga.com",
        "subdomain": "br",
    },
}
language = "en"

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

def cleanHtml(html):
    text = html2text.html2text(html)
    text = text.replace('\n', '')
    text = text.replace('*', '')
    text = text.replace('#', '')
    text = text.replace('_', '')
    return text

def getEntireDomain():
    return f"https://{config_map[language]['subdomain']}.{config_map[language]['domain']}"

def getEndpointPageContent(endpoint):
    url = f"{getEntireDomain()}{endpoint}"
    response = getUriContent(url)
    content = response.content.decode('utf-8')
    return content.replace('\n', '')

def removeDomain(url):
    return url.replace(f"{getEntireDomain()}", '')

def search():
    manga_name = typer.prompt("Enter manga name to search")
    typer.secho(f"Searching: {manga_name}", fg=typer.colors.YELLOW, bg=typer.colors.BLACK)
    endpoint = f"/search/ajax/?term={manga_name}"
    content = getEndpointPageContent(endpoint)
    return list([manga_name, json.loads(content)])

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

def describeChaptersList(content):
    return re.findall(r'<ul class="sub_vol_ul" id="(.+?)">(.+?)</ul>', content)

def requestChaptersList(endpoint):
    content = getEndpointPageContent(endpoint)
    list_content = describeChaptersList(content)
    if(len(list_content) == 0):
        warning_message = re.findall(r'<div class="warning">(.+?)</div>', content) 
        if(len(warning_message) > 0):
            print(cleanHtml(warning_message[0]))
            is_continuing = typer.prompt("Do you want to continue? [y/n]")
            if(is_continuing == 'y'):
                return requestChaptersList(f"{endpoint}?waring=1")
    return list_content

def getChaptersInfo(manga, list_content):
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

def getChaptersList(manga):
    list_content = requestChaptersList(f"/manga/{manga["endpoint"]}.html")
    chapters = []
    if(len(list_content) > 0):
        chapters = getChaptersInfo(manga, list_content)
    manga["chapters"] = chapters
    return manga

def getChaptersContent(manga):
    for i in track(range(len(manga["chapters"])), description="Listing Chapters..."):
        if(len(manga["chapters"][i]["pages"]) == 0):
            print(f"   [{i+1}/{len(manga['chapters'])}] Listing {manga['chapters'][i]['name']} chapter content. 📥")
            pages = getChapterContent(manga["chapters"][i])
            manga["chapters"][i]["pages"] = pages
        else:
            print(f"   [{i+1}/{len(manga["chapters"])}] {manga["chapters"][i]['name']} chapter content already cached! ✅")
        writeMangaDataFile(manga)
    return manga

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
    if not os.path.isdir(data_path):
        createFolder(data_path)
    if not os.path.isdir(f"{data_path}/{language}"):
        createFolder(f"{data_path}/{language}")
    manga_path = f"{data_path}/{language}/{manga['name']}"
    createFolder(manga_path)
    return manga_path

def getMangaDataFilePath(manga):
    path = getMangaPath(manga)
    return f"{path}/{data_json_file}"

def writeMangaDataFile(manga):
    manga["last_update"] = str(datetime.now())
    with open(getMangaDataFilePath(manga), 'w') as fp:
        json.dump(manga, fp)

def readMangaDataFile(manga):
    with open(getMangaDataFilePath(manga), 'r') as fp:
        return json.load(fp)

def numberWithPrefixes(number, total):
    return str(number).rjust(len(str(total)), '0')

def getChapterPDFFilename(folder_name):
    return f"{folder_name}.pdf"

def writePDF(folder_name):
    # Get list of images in the folder
    images = [f for f in os.listdir(folder_name) if f.endswith('.jpg') or f.endswith('.png') or f.endswith('.webp')]

    # Create a new canvas object
    c = canvas.Canvas(getChapterPDFFilename(folder_name))

    for image_file in images:
        # Open image file
        img = Image.open(os.path.join(folder_name, image_file))
        # Get image dimensions
        width, height = img.size

        # Set page size to image size
        c.setPageSize((width, height))

        # Draw image on canvas at full size
        c.drawImage(os.path.join(folder_name, image_file), 0, 0, width=width, height=height)

        # Move to next page
        c.showPage()

    # Save PDF file
    c.save()

def downloadManga(manga):
    for i in range(len(manga["chapters"])):
        manga_path = getMangaPath(manga)
        folder_path = f"{manga_path}/{numberWithPrefixes(i+1, len(manga["chapters"]))} - {manga["chapters"][i]["name"]}"

        files_counter = 0

        # Verify if directory of manga chapter exists
        if os.path.isdir(folder_path):
            # Get the list of files existing on that directory
            files = os.listdir(folder_path)
            
            # Counts list of files existing
            files_counter = len(files)
        else:

            # Creates the manga chapter folder to download the pages images
            createFolder(folder_path)

        # If some pages of chapter is missing download the entire chapter again
        if(files_counter != len(manga["chapters"][i]["pages"])):
            typer.secho(f"Downloading Chapter: {manga["chapters"][i]["name"]}", fg=typer.colors.GREEN, bg=typer.colors.BLACK)
            for j in track(range(len(manga["chapters"][i]["pages"]))):
                content = getEndpointPageContent(manga["chapters"][i]["pages"][j]["endpoint"])
                page_url = re.findall(r'<img class="manga_pic manga_pic_1" id="manga_pic_1" i="1" e="1" src="(.+?)" border="0" />', content)
                image_response = getUriContent(page_url[0])
                fp = open(f"{folder_path}/{numberWithPrefixes(j, len(manga["chapters"][i]["pages"]))}.webp", 'wb')
                fp.write(image_response.content)
                fp.close()

        if not os.path.isfile(getChapterPDFFilename(folder_path)):
            # Writes a PDF file with all content of the directory
            writePDF(folder_path)

def syncChaptersListWithCache(manga):
    data = {"chapters": []}
    if os.path.isfile(getMangaDataFilePath(manga)):
        data = readMangaDataFile(manga)

    for i in range(len(manga["chapters"])):
        try:
            item = next(item for item in data["chapters"] if item["name"] == manga["chapters"][i]["name"])
            manga["chapters"][i]["pages"] = item["pages"]
        except StopIteration:
            manga["chapters"][i]["pages"] = []

    writeMangaDataFile(manga)

    # Get server manga content
    manga = getChaptersContent(manga)
    return manga

def selectLanguage():
    globals()["language"] = typer.prompt("Select the language [en/es/pt]")
    if(language != "en" and language != "es" and language != "pt"):
        typer.secho(f"Language {language} not suported!", fg=typer.colors.RED, bg=typer.colors.BLACK)
        exit()
        
def main():
    typer.secho(f"Nine Manga Crawler!", fg=typer.colors.WHITE, bg=typer.colors.BLUE)

    # Select the manga language
    selectLanguage()

    # Search manga by text
    manga_name, results = search()

    # If serach got results
    if(len(results) > 0):

        # Select one maga from list
        manga = select(results)

        # Get server manga list
        manga = getChaptersList(manga)

        # Compare saved chapters list with online chapters list
        manga = syncChaptersListWithCache(manga)

        # Save/Update manga cache data
        manga["last_update"] = str(datetime.now())
        writeMangaDataFile(manga)

        # Download manga content
        downloadManga(manga)

        typer.secho(f"Download Finished!", fg=typer.colors.WHITE, bg=typer.colors.GREEN)
    else :
        typer.secho(f"No results for: {manga_name}", fg=typer.colors.RED, bg=typer.colors.BLACK)

if __name__ == "__main__":
    typer.run(main)