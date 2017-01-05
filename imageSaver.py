# -*- coding: utf-8 -*-

import urllib
import datetime
import os
import random
from operator import attrgetter
from zlib import crc32
import sys
import imgurpython as imgur

SupportedTypes = ['jpg', 'jpeg', 'gif', 'png', 'webm', 'mp4']

def getFileTypeFromUrl(url):
    if url and url.find('.') != -1 and url.rfind('.') > url.rfind('/'):
        return url[url.rfind('.') + 1:]
    else:
        return ''

# Helper function. Print percentage complete
def percentageComplete(currentItem, numItems):
    if numItems:
        return str(int(((float(currentItem + 1) / float(numItems)) * 100))) + '%'

    return 'Invalid'

def isUrlSupportedType(url):
    urlFileType = getFileTypeFromUrl(url)
    return urlFileType in SupportedTypes

def getUrlContentType(url):
    if url:
        openedUrl = urllib.urlopen(url)
        return openedUrl.info().subtype
    return ''

def isContentTypeSupported(contentType):
    # JPGs are JPEG
    supportedTypes = SupportedTypes + ['jpeg']
    return contentType.lower() in supportedTypes

def convertContentTypeToFileType(contentType):
    # Special case: we want all our JPEGs to be .jpg :(
    if contentType.lower() == 'jpeg':
        return 'jpg'

    return contentType

# Find the source of an image by reading the url's HTML, looking for sourceKey
# An example key would be '<img src='. Note that the '"' will automatically be 
#  recognized as part of the key, so do not specify it
# If sourceKeyAttribute is specified, sourceKey will first be found, then 
#  the line will be searched for sourceKeyAttribute (e.g. sourceKey = '<img' and 
#  sourceKeyAttribute = 'src=').
def findSourceFromHTML(url, sourceKey, sourceKeyAttribute=''):
    SANE_NUM_LINES = 30

    # Open the page to search for a saveable .gif or .webm
    pageSource = urllib.urlopen(url)
    pageSourceLines = pageSource.readlines()
    pageSource.close()

    # If a page has fewer than this number of lines, there is something wrong.
    # This is a somewhat arbitrary heuristic
    if len(pageSourceLines) <= SANE_NUM_LINES:
        print 'Url "' + url + '" has a suspicious number of lines (' + str(len(pageSourceLines)) + ')'

    for line in pageSourceLines:
        foundSourcePosition = line.lower().find(sourceKey.lower())
        
        if foundSourcePosition > -1:
            urlStartPosition = -1
            if sourceKeyAttribute:
                attributePosition = line[foundSourcePosition:].lower().find(sourceKeyAttribute.lower())
                # Find the first character of the URL specified by the attribute (add 1 for the ")
                urlStartPosition = foundSourcePosition + attributePosition + len(sourceKeyAttribute) + 1
            else:
                # Find the first character of the URL (add 1 for the ")
                urlStartPosition = foundSourcePosition + len(sourceKey) + 1

            # From the start of the url, search for the next '"' which is the end of the src link
            urlEndPosition = line[urlStartPosition:].find('"')

            if urlEndPosition > -1:
                sourceUrl = line[urlStartPosition:urlStartPosition + urlEndPosition]

                return sourceUrl

    return ''

def isGfycatUrl(url):
    return 'gfycat' in url.lower()

# Special handling for Gfycat links
# Returns a URL to a webm which can be downloaded by urllib
def convertGfycatUrlToWebM(url):
    # Change this:
    #   https://gfycat.com/IndolentScalyIncatern
    # Into this:
    #   https://zippy.gfycat.com/IndolentScalyIncatern.webm
    # Or maybe this:
    #   https://giant.gfycat.com/IndolentScalyIncatern.webm

    # Look for this key in the HTML document and get whatever src is
    GFYCAT_SOURCE_KEY = '<source id="webmSource" src='

    return findSourceFromHTML(url, GFYCAT_SOURCE_KEY)

def isGifVUrl(url):
    return getFileTypeFromUrl(url) == 'gifv'

# Special handling for Imgur's .gifv
def convertGifVUrlToWebM(url):
    # Find the source link
    GIFV_SOURCE_KEY = '<source src='
    gifvSource = findSourceFromHTML(url, GIFV_SOURCE_KEY)

    # Didn't work? Try the alternate key
    if not gifvSource:
        ALTERNATE_GIFV_SOURCE_KEY = '<meta itemprop="contentURL" content='
        gifvSource = findSourceFromHTML(url, ALTERNATE_GIFV_SOURCE_KEY)

    # Still nothing? Try text hacking .mp4 onto the link and hope it's valid
    if not gifvSource:
        gifvSource = url[:-5] + '.mp4'

    # For whatever reason, Imgur has this screwy no http(s) on their source links sometimes
    if gifvSource and gifvSource[:2] == '//':
        gifvSource = 'http:' + gifvSource

    return gifvSource

def isImgurIndirectUrl(url):
    # If it is imgur domain, has no file type, and isn't an imgur album
    return ('imgur' in url.lower() 
        and not getFileTypeFromUrl(url) 
        and not '/a/' in url)

def convertImgurIndirectUrlToImg(url):
    IMGUR_INDIRECT_SOURCE_KEY = '<link rel="image_src"'
    IMGUR_INDIRECT_SOURCE_KEY_ATTRIBUTE = 'href='
    
    return findSourceFromHTML(url, IMGUR_INDIRECT_SOURCE_KEY, sourceKeyAttribute = IMGUR_INDIRECT_SOURCE_KEY_ATTRIBUTE)

def isImgurAlbumUrl(url):
    # If it is imgur domain, has no file type, is an imgur album, and isn't a single image
    return ('imgur' in url.lower()
        and not getFileTypeFromUrl(url) 
        and '/a/' in url
        and not '#' in url)

def getURLSFromFile(filename):
    f = open(filename, 'r')
    urls = []
    nonRelevantURLs = 0
    
    for line in f:
        if isUrlSupportedType(line):
            urls.append(line[:-1]) #trim off the newline
        else:
            nonRelevantURLs += 1

    print 'Filtered ' + str(nonRelevantURLs) + ' URLs that didn\'t contain images'
    return urls

def saveAllImagesToDir(urls, directory, soft_retrieve = True):
    count = 0
    imagesToSave = len(urls)
    for url in urls:
        if not soft_retrieve:
            urllib.urlretrieve(url, directory + '/img' + str(count) + url[-4:])

        count += 1
        print ('[' + str(int((float(count) / float(imagesToSave)) * 100)) + '%] ' 
            + url + ' saved to "' + directory + '/img' + str(count) + url[-4:] + '"')

def makeDirIfNonexistant(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        
#note that you must explicitly set soft_retrieve to False to actually get the images
def saveAllImages(soft_retrieve_imgs=True):
    saved_urls = getURLSFromFile('savedURLS.txt')
    liked_urls = getURLSFromFile('likedURLS.txt')
    timestamp = datetime.datetime.now().strftime('%m-%d_%H-%-M-%S')
    count = 0
    savedDirectory = 'ImagesSaved__' + timestamp
    likedDirectory = 'ImagesLiked__' + timestamp

    makeDirIfNonexistant(savedDirectory)
    makeDirIfNonexistant(likedDirectory)

    saveAllImagesToDir(saved_urls, savedDirectory, soft_retrieve = soft_retrieve_imgs)
    saveAllImagesToDir(liked_urls, likedDirectory, soft_retrieve = soft_retrieve_imgs)

# Make sure the filename is alphanumeric or has supported symbols, and is shorter than 45 characters
def safeFileName(filename):
    acceptableChars = ['_', ' ']
    safeName = ''
    for char in filename:
        if char.isalnum() or char in acceptableChars:
            safeName += char

    # If there were no valid characters, give it a random number for a unique title
    if not safeName:
        safeName = 'badName_' + str(random.randint(1, 1000000))

    MAX_NAME_LENGTH = 45
    if len(safeName) > MAX_NAME_LENGTH:
        safeName = safeName[:MAX_NAME_LENGTH]

    return safeName

# Returns whether or not there are credits remaining
def checkImgurAPICredits(imgurClient):
    print('Imgur API Credit Report:\n'
        + '\tUserRemaining: ' + str(imgurClient.credits['UserRemaining'])
        + '\n\tClientRemaining: ' + str(imgurClient.credits['ClientRemaining']))

    if not imgurClient.credits['UserRemaining']:
        print('You have used up all of your Imgur API credits! Please wait an hour')
        return False

    # Ensure that this user doesn't suck up all the credits (remove this if you're an asshole)
    if imgurClient.credits['ClientRemaining'] < 1000:
        print('RedditLikedSavedImageDownloader Imgur Client is running low on Imgur API credits!\n'
            'Unfortunately, this means no one can download any Imgur albums until the end of the month.\n'
            'If you are really jonesing for access, authorize your own Imgur Client and fill in its details in settings.txt.')
        return False

    return True

class ImgurAuth:
    def __init__(self, clientId, clientSecret):
        self.clientId = clientId
        self.clientSecret = clientSecret

def saveAllImgurAlbums(outputDir, imgurAuth, subredditAlbums, soft_retrieve_imgs = True):
    numSavedAlbumsTotal = 0

    # Login to imgur
    imgurClient = imgur.ImgurClient(imgurAuth.clientId, imgurAuth.clientSecret)

    if not checkImgurAPICredits(imgurClient):
        return 0

    if not soft_retrieve_imgs:
        makeDirIfNonexistant(outputDir)

    subredditIndex = -1
    numSubreddits = len(subredditAlbums)
    for subredditDir, albums in subredditAlbums.iteritems():
        subredditIndex += 1
        print('[' + percentageComplete(subredditIndex, numSubreddits) + '] ' 
            + subredditDir)

        if not soft_retrieve_imgs:
            # Make directory for subreddit
            makeDirIfNonexistant(outputDir + '/' + subredditDir)

        numAlbums = len(albums)
        for albumIndex, album in enumerate(albums):
            albumTitle = album[0]
            albumUrl = album[1]
            print('\t[' + percentageComplete(albumIndex, numAlbums) + '] ' 
                + '\t' + albumTitle + ' (' + albumUrl + ')')

            # Example path:
            # output/aww/Cute Kittens_802984323
            # output/subreddit/Submission Title_urlCRC
            # The CRC is used so that if we are saving two albums with the same
            #  post title (e.g. 'me_irl') we get unique folder names because the URL is different
            saveAlbumPath = (outputDir + u'/' + subredditDir + u'/' 
                + safeFileName(albumTitle) + u'_' + unicode(crc32(albumUrl)))

            # If we already saved the album, skip it
            # Note that this means updating albums will not be updated
            if os.path.isdir(saveAlbumPath):
                print ('\t\t[already saved] ' + 'Skipping album ' + albumTitle 
                    + ' (note that this script will NOT update albums)')
                continue

            if not soft_retrieve_imgs:
                # Make directory for album
                makeDirIfNonexistant(saveAlbumPath)            

            albumImages = []
            # Don't talk to the API for soft retrieval (we don't want to waste our credits)
            if not soft_retrieve_imgs:
                # Request the list of images from Imgur
                albumStartId = albumUrl.find('/a/') + 3
                albumEndId = albumUrl[albumStartId:].find('/')
                if albumEndId != -1:
                    albumId = albumUrl[albumStartId:albumStartId + albumEndId]
                else:
                    albumId = albumUrl[albumStartId:]

                albumImages = imgurClient.get_album_images(albumId)

            if not albumImages:
                continue

            numImages = len(albumImages)
            for imageIndex, image in enumerate(albumImages):
                imageUrl = image.link
                fileType = getFileTypeFromUrl(imageUrl)
                saveFilePath = saveAlbumPath + u'/' + str(imageIndex) + '.' + fileType

                if not soft_retrieve_imgs:
                    # Retrieve the image and save it
                    urllib.urlretrieve(imageUrl, saveFilePath)

                print ('\t\t[' + percentageComplete(imageIndex, numImages) + '] ' 
                    + ' [save] ' + imageUrl + ' saved to "' + saveAlbumPath + '"')

            numSavedAlbumsTotal += 1

    return numSavedAlbumsTotal


# Save the images in directories based on subreddits
# Name the images based on their submission titles
# Returns a list of submissions which didn't have supported image formats
def saveAllImages_Advanced(outputDir, submissions, imgur_auth = None, 
                           soft_retrieve_imgs = True, only_important_messages = False):
    numSavedImages = 0
    numAlreadySavedImages = 0
    numUnsupportedImages = 0
    numUnsupportedAlbums = 0

    unsupportedSubmissions = []

    # Dictionary where key = subreddit and value = list of (submissionTitle, imgur album urls)
    imgurAlbumsToSave = {}

    if not soft_retrieve_imgs:
        makeDirIfNonexistant(outputDir)
    
    # Sort by subreddit, alphabetically
    sortedSubmissions = sorted(submissions, key=attrgetter('subreddit'))
    submissionsToSave = len(sortedSubmissions)

    for currentSubmissionIndex, submission in enumerate(sortedSubmissions):
        url = submission.bodyUrl
        subredditDir = submission.subreddit[3:-1]
        submissionTitle = submission.title

        if not url:
            continue

        # Imgur Albums have special handling
        if isImgurAlbumUrl(url):
            if not imgur_auth:
                print ('[' + percentageComplete(currentSubmissionIndex, submissionsToSave) + '] '
                    + ' [unsupported] ' + 'Skipped "' + url + '" (imgur album)')
                numUnsupportedAlbums += 1
                continue
            else:
                # We're going to save Imgur Albums at a separate stage
                if subredditDir in imgurAlbumsToSave:
                    imgurAlbumsToSave[subredditDir].append((submissionTitle, url))
                else:
                    imgurAlbumsToSave[subredditDir] = [(submissionTitle, url)]
                continue

        # Massage special-case links so that they can be downloaded
        if isGfycatUrl(url):
            url = convertGfycatUrlToWebM(url)
        if isGifVUrl(url):
            url = convertGifVUrlToWebM(url)
        if isImgurIndirectUrl(url):
            url = convertImgurIndirectUrlToImg(url)

        urlContentType = getUrlContentType(url)
        if isUrlSupportedType(url) or isContentTypeSupported(urlContentType):
            fileType = getFileTypeFromUrl(url)
            if not fileType:
                fileType = convertContentTypeToFileType(urlContentType)

            # If the file path doesn't match the content type, it's possible it's incorrect 
            #  (e.g. a .png labeled as a .jpg)
            contentFileType = convertContentTypeToFileType(urlContentType)
            if contentFileType != fileType and (contentFileType != 'jpg' and fileType != 'jpeg'):
                print ('WARNING: Content type "' + contentFileType + '" was going to be saved as "' + fileType + '"! Correcting.')
                if contentFileType == 'html':
                    print ('[' + percentageComplete(currentSubmissionIndex, submissionsToSave) + '] '
                        + ' [unsupported] ' + 'Skipped "' + url 
                        + '" (file is html, not image; this might mean Access was Denied)')
                    numUnsupportedImages += 1
                    continue

            # Example path:
            # output/aww/My Cute Kitten_802984323.png
            # output/subreddit/Submission Title_urlCRC.fileType
            # The CRC is used so that if we are saving two images with the same
            #  post title (e.g. 'me_irl') we get unique filenames because the URL is different
            saveFilePath = (outputDir + u'/' + subredditDir + u'/' 
                + safeFileName(submissionTitle) + u'_' + unicode(crc32(url)) + u'.' + fileType)

            # If we already saved the image, skip it
            if os.path.isfile(saveFilePath):
                if not only_important_messages:
                    print ('[' + percentageComplete(currentSubmissionIndex, submissionsToSave) + '] ' 
                        + ' [already saved] ' + 'Skipping ' + saveFilePath)
                numAlreadySavedImages += 1
                continue

            if not soft_retrieve_imgs:
                # Make directory for subreddit
                makeDirIfNonexistant(outputDir + '/' + subredditDir)

                # Retrieve the image and save it
                urllib.urlretrieve(url, saveFilePath)

            # Output our progress
            print ('[' + percentageComplete(currentSubmissionIndex, submissionsToSave) + '] ' 
                    + ' [save] ' + url + ' saved to "' + subredditDir + '"')
            numSavedImages += 1

        else:
            print ('[' + percentageComplete(currentSubmissionIndex, submissionsToSave) + '] '
                + ' [unsupported] ' + 'Skipped "' + url + '" (content type "' + urlContentType + '")')
            unsupportedSubmissions.append(submission)
            numUnsupportedImages += 1

    numSavedAlbums = 0
    if imgur_auth and imgurAlbumsToSave:
        numSavedAlbums = saveAllImgurAlbums(outputDir, imgur_auth, imgurAlbumsToSave, 
            soft_retrieve_imgs = soft_retrieve_imgs)

    print('Good:')
    print('\t numSavedImages: ' + str(numSavedImages))
    print('\t numAlreadySavedImages: ' + str(numAlreadySavedImages))
    print('\t numSavedAlbums: ' + str(numSavedAlbums))
    print('Bad:')
    print('\t numUnsupportedImages: ' + str(numUnsupportedImages))
    print('\t numUnsupportedAlbums: ' + str(numUnsupportedAlbums))

    return unsupportedSubmissions