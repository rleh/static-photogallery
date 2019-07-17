#!/usr/bin/env python3

import glob, os
import collections
import jinja2
import shutil
from PIL import Image
from multiprocessing import Pool 
import argparse

parser = argparse.ArgumentParser(description='Statically generated photogallery')
parser.add_argument('source', type=str, help='Source directory of images.')
parser.add_argument('-o', '--output', type=str, default='./html/',
	help='Destination directory for generated HTML and thumbnails.')
parser.add_argument('-s', '--static', type=str, default="",
	help='Web URL (absolute path) to static folder.')
args = parser.parse_args()

GalleryItem = collections.namedtuple('GalleryItem', 'name dir path thumbnail_small thumbnail_large')
templateLoader = jinja2.FileSystemLoader(searchpath="./")
templateEnv = jinja2.Environment(loader=templateLoader)

rootpath = args.source
output_path = args.output + '/'
output_static_path = os.path.join(output_path, 'static')
output_thumbnail_path = output_path
web_static_path = args.static

def recurse_files(path):
    item_list = []
    dir_list = []
    for inode in glob.iglob(path + '/**', recursive=False):
        if os.path.isfile(inode):
            thumbnail, thumbnail_large = generate_thumbnail(inode)
            item_list.append(GalleryItem(os.path.relpath(inode, path), False, inode, thumbnail, thumbnail_large))
        elif os.path.isdir(inode):
            #item_list.append(GalleryItem(os.path.relpath(inode, path), True, inode, 'folder-icon', 'folder-icon'))
            dir_list.append(str(os.path.basename(inode)))
            recurse_files(inode)
        else:
            print(inode + " is neither a file nor a directory. Skipping...")
    #print("OUT: " + path + " -> " + " | ".join(str(i) for i in item_list))
    generate_gallery_page(path, item_list, dir_list)

def generate_gallery_page(path, item_list, dir_list):
    if web_static_path is "":
        static_relpath = os.path.relpath(output_static_path, path)
    else:
        static_relpath = web_static_path
    template = templateEnv.get_template('gallery_page.html.jinja2')
    os.makedirs(os.path.join(output_path, os.path.relpath(path, rootpath)), exist_ok=True)

    item_list_html = []
    for item in item_list:
        item_path = os.path.join(rootpath, os.path.relpath(item.path, path))
        thumbnail_small = os.path.relpath(item.thumbnail_small, path)
        thumbnail_large = os.path.relpath(item.thumbnail_large, path)
        item_list_html.append(GalleryItem(item.name, False, item_path, os.path.basename(thumbnail_small), os.path.basename(thumbnail_large)))

    filename = os.path.join(output_path, os.path.relpath(path, rootpath), 'index.html')
    with open(filename, 'w') as fh:
        fh.write(template.render(items=item_list_html, dirs=dir_list, page_title=path, static_path=static_relpath))


ThumbnailItem = collections.namedtuple('ThumbnailItem', 'src small large')
thumbnail_list = []

def generate_thumbnail(image):
    destination = os.path.join(output_thumbnail_path, os.path.relpath(image, rootpath))
    directory, _ = os.path.split(destination)
    os.makedirs(directory, exist_ok=True)
    small = destination + '.small.jpg'
    large = destination + '.large.jpg'
    thumbnail_list.append(ThumbnailItem(image, small, large))
    return small, large

def process_thumbnail(param):
	# TODO: Check if thumbnail already exists
    try:
        im = Image.open(param.src)
        im.thumbnail((1920,1200))
        im.save(param.large)
        im.thumbnail((400,250))
        im.save(param.small)
        return True
    except Exception as e:
        print('Error while creating thumbnail for image {}: {}'.format(param.src, str(e)))
        return e

def batch_process_thumbnails():
    pool = Pool(8)
    results = pool.map(process_thumbnail, thumbnail_list)

def copy_static_files():
    destination = output_static_path
    if os.path.exists(destination):
        shutil.rmtree(destination)
    shutil.copytree('./static/', destination)

if __name__ == "__main__":
    recurse_files(rootpath)
    copy_static_files()
    batch_process_thumbnails()
