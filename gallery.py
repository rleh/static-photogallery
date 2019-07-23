#!/usr/bin/env python3

import glob, os
import collections
import jinja2
import shutil
from PIL import Image, ExifTags
from multiprocessing import Pool
import argparse

parser = argparse.ArgumentParser(description='Statically generated photogallery')
parser.add_argument('source', type=str, help='Source directory of images.')
parser.add_argument('-d', '--destination', type=str, default='./html/',
    help='Destination directory for generated HTML and thumbnails.')
parser.add_argument('-s', '--static', type=str, default="",
    help='Web URL (absolute path) to static folder.')
parser.add_argument('-o', '--original', type=str, default="",
    help='Web URL (absolute path) to original images.')
parser.add_argument('-j', '--jobs', type=int, default=8,
    help='Specifies the number of thumbnail generation jobs to run simultaneously.')
parser.add_argument('-t', '--title', type=str, default="Static Photogallery",
    help='Prefix for the HTML page title.')
args = parser.parse_args()

GalleryItem = collections.namedtuple('GalleryItem', 'name dir path thumbnail_small thumbnail_large')
templateLoader = jinja2.FileSystemLoader(searchpath="./")
templateEnv = jinja2.Environment(loader=templateLoader)

rootpath = args.source
output_path = args.destination + '/'
output_static_path = os.path.join(output_path, 'static')
output_thumbnail_path = output_path
web_static_path = args.static
web_original_path = args.original

def recurse_files(path):
    item_list = []
    dir_list = []
    hash_list = []
    for inode in sorted(glob.iglob(path + '/**', recursive=False)):
        hash_list.append((os.path.basename(inode), os.path.getmtime(inode)))
        if os.path.isfile(inode):
            thumbnail, thumbnail_large = generate_thumbnail(inode)
            item_list.append(GalleryItem(os.path.relpath(inode, path), False, inode, thumbnail, thumbnail_large))
        elif os.path.isdir(inode):
            #item_list.append(GalleryItem(os.path.relpath(inode, path), True, inode, 'folder-icon', 'folder-icon'))
            dir_list.append(str(os.path.basename(inode)))
            recurse_files(inode)
        else:
            print(inode + " is neither a file nor a directory. Skipping...")
    generate_gallery_page(path, item_list, dir_list, str(hash(frozenset(hash_list))))

def generate_gallery_page(path, item_list, dir_list, directory_hash):
    if web_static_path is "":
        static_relpath = os.path.relpath(output_static_path, path)
    else:
        static_relpath = web_static_path
    template = templateEnv.get_template('gallery_page.html.jinja2')
    os.makedirs(os.path.join(output_path, os.path.relpath(path, rootpath)), exist_ok=True)

    item_list_html = []
    for item in item_list:
        item_path = os.path.relpath(item.path, rootpath)
        thumbnail_small = os.path.relpath(item.thumbnail_small, path)
        thumbnail_large = os.path.relpath(item.thumbnail_large, path)
        item_list_html.append(GalleryItem(item.name, False, item_path, os.path.basename(thumbnail_small), os.path.basename(thumbnail_large)))

    filename = os.path.join(output_path, os.path.relpath(path, rootpath), 'index.html')
    with open(filename, 'w') as fh:
        fh.write(template.render(
            items=item_list_html,
            dirs=dir_list,
            page_title=os.path.basename(path),
            page_title_prefix=args.title,
            static_path=static_relpath,
            original_path=web_original_path,
            )
        )


ThumbnailItem = collections.namedtuple('ThumbnailItem', 'src small large')
thumbnail_list = []

def generate_thumbnail(image):
    destination = os.path.join(output_thumbnail_path, os.path.relpath(image, rootpath))
    directory, _ = os.path.split(destination)
    os.makedirs(directory, exist_ok=True)
    small = destination + '.small.jpg'
    large = destination + '.large.jpg'
    if (not os.path.isfile(small)) or (not os.path.isfile(large)):
        thumbnail_list.append(ThumbnailItem(image, small, large))
    return small, large

def process_thumbnail(param):
    try:
        im = Image.open(param.src)
        if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
            # Need to convert to RGBA if LA format due to a bug in PIL (http://stackoverflow.com/a/1963146)
            alpha = im.convert('RGBA').getchannel('A')
            im = im.convert('RGB')

        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation': break
        exif = dict(im._getexif().items())

        if exif[orientation] == 3:
            im = im.rotate(180, expand=True)
        elif exif[orientation] == 6:
            im = im.rotate(270, expand=True)
        elif exif[orientation] == 8:
            im = im.rotate(90, expand=True)

        im.thumbnail((1920,1200),Image.ANTIALIAS)
        im.save(param.large,optimize=True,quality=85)
        im.thumbnail((400,250),Image.ANTIALIAS)
        im.save(param.small,optimize=True,quality=70)
        return True
    except Exception as e:
        print('Error while creating thumbnail for image {}: {}'.format(param.src, str(e)))
        shutil.copyfile('./static/no-thumbnail.jpg', param.small)
        shutil.copyfile('./static/no-thumbnail.jpg', param.large)
        return e

def batch_process_thumbnails():
    pool = Pool(args.jobs)
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
