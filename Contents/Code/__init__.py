import string
from ss import Downloader
from ss import util
from ss import DownloadStatus
#util.redirect_output('/Users/mike/Work/other/ss-plex.bundle/out')

PLUGIN_PREFIX = '/video/ssp'
PLUGIN_TITLE  = L('title')
PLUGIN_ART    = 'art-default.jpg'
PLUGIN_ICON   = 'icon-default.png'

def Start():
    # Initialize the plug-in
    Plugin.AddViewGroup('Details',  viewMode = 'InfoList',  mediaType = 'items')
    Plugin.AddViewGroup('List',     viewMode = 'List',      mediaType = 'items')

    ObjectContainer.view_group = 'List'
    ObjectContainer.art        = R(PLUGIN_ART)
    DirectoryObject.art        = R(PLUGIN_ART)

def ValidatePrefs(): pass

@handler(PLUGIN_PREFIX, PLUGIN_TITLE, thumb = PLUGIN_ICON, art = PLUGIN_ART)
def MainMenu():
    container = render_listings('/')

    container.add(button('heading.favorites',    FavoritesIndex, icon = 'icon-favorites.png'))
    container.add(input_button('heading.search', 'search.prompt', SearchResults, icon = 'icon-search.png', foo = 1))
    container.add(button('search.heading.saved', SearchIndex, icon = 'icon-saved-search.png'))
    container.add(button('heading.download',     DownloadsIndex, refresh = 0, icon = 'icon-downloads.png'))
    container.add(button('heading.system',       SystemIndex, icon = 'icon-system.png'))

    return container

##########
# System #
##########

@route('%s/system' % PLUGIN_PREFIX)
def SystemIndex():
    container = ObjectContainer(title1 = L('heading.system'))

    container.add(PrefsObject(title = L('system.heading.preferences')))
    container.add(confirm('system.heading.reset-favorites',        SystemConfirmResetFavorites))
    container.add(confirm('system.heading.reset-search',           SystemConfirmResetSearches))
    container.add(confirm('system.heading.reset-download-history', SystemConfirmResetDownloads))
    container.add(confirm('system.heading.reset-factory',          SystemConfirmResetFactory))
    container.add(button('system.heading.dispatch-force',          DownloadsDispatchForce))
    container.add(button('version %s' % util.version.string, SystemIndex))

    return container

@route('%s/system/confirm/reset-favorites' % PLUGIN_PREFIX)
def SystemConfirmResetFavorites(): return warning('system.warning.reset-favorites', 'confirm.yes', SystemResetFavorites)

@route('%s/system/confirm/reset-searches' % PLUGIN_PREFIX)
def SystemConfirmResetSearches(): return warning('system.warning.reset-search', 'confirm.yes', SystemResetSearches)

@route('%s/system/confirm/reset-downloads' % PLUGIN_PREFIX)
def SystemConfirmResetDownloads(): return warning('system.warning.reset-download-history', 'confirm.yes', SystemResetDownloads)

@route('%s/system/confirm/reset-factory' % PLUGIN_PREFIX)
def SystemConfirmResetFactory(): return warning('system.warning.reset-factory', 'confirm.yes', SystemResetFactory)

@route('%s/system/reset/favorites' % PLUGIN_PREFIX)
def SystemResetFavorites():
    User.clear_favorites()
    return dialog('heading.system', 'system.response.reset-favorites')

@route('%s/system/reset/searches' % PLUGIN_PREFIX)
def SystemResetSearches():
    User.clear_searches()
    return dialog('heading.system', 'system.response.reset-search')

@route('%s/system/reset/downloads' % PLUGIN_PREFIX)
def SystemResetDownloads():
    User.clear_download_history()
    return dialog('heading.system', 'system.response.reset-download-history')

@route('%s/system/reset/factory' % PLUGIN_PREFIX)
def SystemResetFactory():
    Dict.Reset()
    return dialog('heading.system', 'system.response.reset-factory')

#############
# Searching #
#############

@route('%s/search' % PLUGIN_PREFIX)
def SearchIndex():
    container = ObjectContainer()

    for query in sorted(User.searches()):
        container.add(button(query, SearchResults, query = query, foo = 1))

    return container

#@route('%s/search/results/{query}' % PLUGIN_PREFIX)
def SearchResults(query, foo):
    container = render_listings('/search/%s' % util.q(query))

    if User.has_saved_search(query): save_label = 'search.heading.remove'
    else:                            save_label = 'search.heading.add'

    container.objects.insert(0, button(save_label, SearchToggle, query = query))

    return container

@route('%s/search/toggle' % PLUGIN_PREFIX)
def SearchToggle(query):
    saved_searches = User.searches()

    if User.has_saved_search(query):
        message = 'search.response.removed'
        saved_searches.remove(query)
    else:
        message = 'search.response.added'
        saved_searches.append(query)

    Dict.Save()
    return dialog('heading.search', message)

#############
# Favorites #
#############

@route('%s/favorites' % PLUGIN_PREFIX)
def FavoritesIndex():
    container = ObjectContainer(
        title1 = 'Favorites'
    )

    if 'favorites' in Dict:
        container.add(button('favorites.heading.migrate', FavoritesMigrate1to2))
    else:
        favorites = User.favorites()
        def sort_title(title):
            import re

            haystack = str(title).lower()
            return re.sub(r'^the ', '', haystack)

        for endpoint, fav in sorted(favorites.iteritems(), key = lambda x: sort_title(x[1]['title'])):
            title  = fav['title']
            native = TVShowObject(
                rating_key = endpoint,
                title      = title,
                thumb      = fav['artwork'],
                key        = Callback(ListTVShow, refresh = 0, endpoint = endpoint, show_title = title)
            )

            container.add(native)

    return container

@route('%s/favorites/toggle' % PLUGIN_PREFIX)
def FavoritesToggle(endpoint, show_title, artwork):
    message = None

    if User.endpoint_is_favorite(endpoint):
        del Dict['favorites2'][endpoint]
        message = 'favorites.response.removed'
    else:
        favorites           = User.favorites()
        favorites[endpoint] = dict(title = show_title, artwork = artwork)
        message             = 'favorites.response.added'

    Dict.Save()

    return dialog('heading.favorites', F(message, show_title))

def FavoritesMigrate1to2():
    @thread
    def migrate():
        if 'favorites' in Dict:
            old_favorites = Dict['favorites']
            new_favorites = User.favorites()

            for endpoint, title in old_favorites.iteritems():
                if endpoint not in new_favorites:
                    try:
                        response = JSON.ObjectFromURL(util.listings_endpoint(endpoint))
                        new_favorites[endpoint] = dict(title = response['display_title'], artwork = response['artwork'])
                    except: pass

            del Dict['favorites']
            Dict.Save()

    migrate()
    return dialog('Favorites', 'Your favorites are being updated. Return shortly.')

###############
# Downloading #
###############

@route('%s/downloads/i{refresh}' % PLUGIN_PREFIX)
def DownloadsIndex(refresh = 0):
    container = ObjectContainer(title1 = L('heading.download'))

    if User.currently_downloading():
        current       = Dict['download_current']
        endpoint      = current['endpoint']
        status        = DownloadStatus(Downloader.status_file_for(endpoint))

        container.add(popup_button(current['title'], DownloadsOptions, endpoint = endpoint, icon = 'icon-downloads.png'))

        for ln in status.report():
            container.add(popup_button(ln, DownloadsOptions, endpoint = endpoint, icon = 'icon-downloads.png'))

    for download in User.download_queue():
        container.add(popup_button(download['title'], DownloadsOptions, endpoint = download['endpoint'], icon = 'icon-downloads-queue.png'))

    add_refresh_to(container, refresh, DownloadsIndex)
    return container

@route('%s/downloads/show' % PLUGIN_PREFIX)
def DownloadsOptions(endpoint):
    download = User.download_for_endpoint(endpoint)

    if download:
        container  = ObjectContainer(title1 = download['title'])
        obj_cancel = button('download.heading.cancel', DownloadsCancel, endpoint = endpoint)

        if User.endpoint_is_downloading(endpoint):
            if not User.pid_running(Dict['download_current']['pid']):
                container.add(button('download.heading.repair', DownloadsDispatchForce))
            else:
                container.add(button('download.heading.next', DownloadsNext))
                container.add(obj_cancel)
        else:
            container.add(obj_cancel)

        return container
    else:
        return dialog('heading.error', F('download.response.not-found', endpoint))

@route('%s/downloads/queue' % PLUGIN_PREFIX)
def DownloadsQueue(endpoint, media_hint, title):
    if User.has_downloaded(endpoint):
        message = 'download.response.exists'
    else:
        message = 'download.response.added'
        User.download_queue().append({
            'title':      title,
            'endpoint':   endpoint,
            'media_hint': media_hint
        })

        Dict.Save()

    #User.dispatch_download()
    dispatch_download_threaded()
    return dialog('heading.download', F(message, title))

@route('%s/downloads/dispatch' % PLUGIN_PREFIX)
def DownloadsDispatch():
    #User.dispatch_download()
    dispatch_download_threaded()

@route('%s/downloads/dispatch/force' % PLUGIN_PREFIX)
def DownloadsDispatchForce():
    User.clear_current_download()
    #User.dispatch_download()
    dispatch_download_threaded()

@route('%s/downloads/cancel' % PLUGIN_PREFIX)
def DownloadsCancel(endpoint):
    download = User.download_for_endpoint(endpoint)

    if download:
        if User.endpoint_is_downloading(endpoint):
            User.signal_download('cancel')
        else:
            try:
                User.download_queue().remove(download)
                Dict.Save()
            except: pass

        return dialog('heading.download', F('download.response.cancel', download['title']))
    else:
        return dialog('heading.error', F('download.response.not-found', endpoint))

@route('%s/downloads/next' % PLUGIN_PREFIX)
def DownloadsNext():
    User.signal_download('next')

#########################
# Development Endpoints #
#########################

@route('%s/test' % PLUGIN_PREFIX)
def QuickTest():
    return ObjectContainer(header = 'Test', message = User.plex_section_destination('movie'))

###################
# Listing Methods #
###################

@route('%s/RenderListings' % PLUGIN_PREFIX)
def RenderListings(endpoint, default_title = None):
    return render_listings(endpoint, default_title)

@route('%s/WatchOptions' % PLUGIN_PREFIX)
def WatchOptions(endpoint, title, media_hint):
    container        = render_listings(endpoint, default_title = title)

    wizard_url       = '//ss/wizard?endpoint=%s&avoid_flv=%s' % (endpoint, int(Prefs['avoid_flv_streaming']))
    wizard_item      = VideoClipObject(title = L('media.watch-now'), url = wizard_url)

    sources_endpoint = util.sources_endpoint(endpoint, True)
    sources_item     = button('media.all-sources', RenderListings, endpoint = sources_endpoint, default_title = title)

    if User.has_downloaded(endpoint):
        download_item = button('media.persisted', DownloadsOptions, endpoint = endpoint)
    else:
        download_item = button('media.watch-later', DownloadsQueue,
            endpoint   = endpoint,
            media_hint = media_hint,
            title      = title
        )

    container.objects.insert(0, wizard_item)
    container.objects.insert(1, download_item)
    container.objects.insert(2, sources_item)

    return container

@route('%s/series/i{refresh}' % PLUGIN_PREFIX)
def ListTVShow(endpoint, show_title, refresh = 0):
    container, response = render_listings(endpoint + '/episodes', show_title, True)

    if User.endpoint_is_favorite(endpoint): favorite_label = 'favorites.heading.remove'
    else:                                   favorite_label = 'favorites.heading.add'

    container.objects.insert(0, button(favorite_label, FavoritesToggle,
        endpoint   = endpoint,
        icon       = 'icon-favorites.png',
        show_title = show_title,
        artwork    = response['resource']['artwork']
    ))

    add_refresh_to(container, refresh, ListTVShow,
        endpoint   = endpoint,
        show_title = show_title,
    )

    return container

def render_listings(endpoint, default_title = None, return_response = False):
    listings_endpoint = util.listings_endpoint(endpoint)

    #response  = JSON.ObjectFromURL(listings_endpoint, headers = { 'Accept-Encoding': 'gzip,deflate,identity' })
    response  = JSON.ObjectFromURL(listings_endpoint)
    container = ObjectContainer(
        title1 = response.get('title') or default_title,
        title2 = response.get('desc')
    )

    for element in response.get( 'items', [] ):
        naitive          = None
        permalink        = element.get('endpoint')
        display_title    = element.get('display_title')    or element.get('title')
        overview         = element.get('display_overview') or element.get('overview')
        tagline          = element.get('display_tagline')  or element.get('tagline')
        element_type     = element.get('_type')
        generic_callback = Callback(RenderListings, endpoint = permalink, default_title = display_title)

        if 'endpoint' == element_type:
            naitive = DirectoryObject(
                title   = display_title,
                tagline = tagline,
                summary = overview,
                key     = generic_callback,
                thumb   = element.get('artwork')
            )

            if '/' == endpoint:
                if 'tv' in display_title.lower():
                    naitive.thumb = R('icon-tv.png')
                elif 'movie' in display_title.lower():
                    naitive.thumb = R('icon-movies.png')

        elif 'show' == element_type:
            naitive = TVShowObject(
                rating_key = permalink,
                title      = display_title,
                summary    = overview,
                thumb      = element.get('artwork'),
                key        = Callback(ListTVShow, refresh = 0, endpoint = permalink, show_title = display_title)
            )

        elif 'movie' == element_type or 'episode' == element_type:
            media_hint = element_type
            if 'episode' == media_hint:
                media_hint = 'show'

            naitive = PopupDirectoryObject(
                title   = display_title,
                tagline = tagline,
                thumb   = element.get('artwork'),
                summary = overview,
                key     = Callback(WatchOptions, endpoint = permalink, title = display_title, media_hint = media_hint)
            )

        elif 'foreign' == element_type:
            final_url = element.get('final_url')

            if final_url:
                service_url = '//ss/procedure?url=%s' % util.q(final_url)
            else:
                service_url = '//ss%s' % util.translate_endpoint(element['original_url'], element['foreign_url'], True)

            naitive = VideoClipObject(title = element['domain'], url = service_url)

        #elif 'final' == element_type:
            #ss_url = '//ss/procedure?url=%s&title=%s' % (util.q(element['url']), util.q('FILE HINT HERE'))
            #naitive = VideoClipObject(url = ss_url, title = display_title)

        #elif 'movie' == element_type:
            #naitive = MovieObject(
                #rating_key = permalink,
                #title      = display_title,
                #tagline    = element.get( 'tagline' ),
                #summary    = element.get( 'desc' ),
                #key        = sources_callback
            #)
        #elif 'episode' == element_type:
            #naitive = EpisodeObject(
                #rating_key     = permalink,
                #title          = display_title,
                #summary        = element.get( 'desc' ),
                #season         = int( element.get( 'season', 0 ) ),
                #absolute_index = int( element.get( 'number', 0 ) ),
                #key            = sources_callback
            #)

        if None != naitive:
            container.add( naitive )

    if return_response:
        return [ container, response ]
    else:
        return container

#######################
# SS Plex Environment #
#######################

class SSPlexEnvironment:
    def log(self,   message):               Log(message)
    def json(self,  payload_url, **params): return JSON.ObjectFromURL(payload_url, values = params)
    def css(self,   haystack,    selector): return HTML.ElementFromString(haystack).cssselect(selector)
    def xpath(self, haystack,    query):    return HTML.ElementFromString(haystack).xpath(query)
    def to_json(self, obj):                 return JSON.StringFromObject(obj)

##################
# Plugin Helpers #
##################

class User(object):
    @classmethod
    def favorites(cls): return cls.initialize_dict('favorites2', {})

    @classmethod
    def searches(cls): return cls.initialize_dict('searches',  [])

    @classmethod
    def download_queue(cls): return cls.initialize_dict('downloads', [])

    @classmethod
    def download_history(cls): return cls.initialize_dict('download_history', [])

    @classmethod
    def currently_downloading(cls): return 'download_current' in Dict

    @classmethod
    def endpoint_is_favorite(cls, endpoint): return endpoint in cls.favorites().keys()

    @classmethod
    def has_saved_search(cls, query): return query in cls.searches()

    @classmethod
    def clear_favorites(cls): cls.attempt_clear('favorites2')

    @classmethod
    def clear_searches(cls): cls.attempt_clear('searches')

    @classmethod
    def clear_download_history(cls): cls.attempt_clear('download_history')

    @classmethod
    def clear_current_download(cls): cls.attempt_clear('download_current')

    @classmethod
    def running_windows(cls):
        import os
        return 'nt' == os.name

    @classmethod
    def pid_running(cls, pid):
        if cls.running_windows():
            return cls.pid_running_windows(pid)
        else:
            return cls.signal_process_unix(pid)

    @classmethod
    def signal_process(cls, pid, to_send = 0):
        if cls.running_windows():
            return cls.signal_process_windows(pid, to_send)
        else:
            return cls.signal_process_unix(pid, to_send)

    @classmethod
    def signal_process_unix(cls, pid, to_send = 0):
        try:
            import os
            os.kill(pid, to_send)
            return True
        except:
            return False

    @classmethod
    def signal_process_windows(cls, pid, to_send = 0):
        try:
            import ctypes
            # 1 == PROCESS_TERMINATE
            handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
            ctypes.windll.kernel32.TerminateProcess(handle, to_send * -1)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except:
            return False

    @classmethod
    def pid_running_windows(cls, pid):
        import ctypes, ctypes.wintypes
        # GetExitCodeProcess uses a special exit code to indicate that the process is
        # still running.
        still_active = 259
        kernel32     = ctypes.windll.kernel32
        handle       = kernel32.OpenProcess(1, 0, pid)

        if handle == 0:
            return False

        # If the process exited recently, a pid may still exist for the handle.
        # So, check if we can get the exit code.
        exit_code  = ctypes.wintypes.DWORD()
        is_running = ( kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0 )
        kernel32.CloseHandle(handle)

        # See if we couldn't get the exit code or the exit code indicates that the
        # process is still running.
        return is_running or exit_code.value == still_active

    @classmethod
    def attempt_clear(cls, key):
        if key in Dict:
            del Dict[key]
            Dict.Save()

    @classmethod
    def initialize_dict(cls, key, default = None):
        if not key in Dict:
            Dict[key] = default

        return Dict[key]


    @classmethod
    def plex_section(cls, section):
        query = '//Directory[@type="%s"]' % section
        dirs  = XML.ElementFromURL('http://127.0.0.1:32400/library/sections').xpath(query)
        for d in dirs:
            if '.none' not in d.get('agent'):
                return d

    @classmethod
    def plex_section_refresh(cls, section):
        element = cls.plex_section(section)
        key     = element.get('key')
        url     = 'http://127.0.0.1:32400/library/sections/%s/refresh' % key

        HTTP.Request(url, immediate = True)

    @classmethod
    def plex_section_destination(cls, section):
        element   = cls.plex_section(section)
        locations = element.xpath('./Location')
        hinted    = locations[0].get('path')
        fragment  = '/ssp'

        for element in locations:
            path = element.get('path')

            if path.endswith(fragment) or path.endswith(fragment + '/'):
                hinted = path
                break

        return hinted

    @classmethod
    def endpoint_is_downloading(cls, endpoint):
        return cls.currently_downloading() and endpoint == Dict['download_current']['endpoint']

    @classmethod
    def has_downloaded(cls, endpoint):
        found = cls.download_for_endpoint(endpoint)

        if found: return True
        else:     return endpoint in cls.download_history()

    @classmethod
    def download_for_endpoint(cls, endpoint):
        if cls.endpoint_is_downloading(endpoint):
            return Dict['download_current']
        else:
            found = filter(lambda h: h['endpoint'] == endpoint, cls.download_queue())

            if found:
                return found[0]

    @classmethod
    def signal_download(cls, sig):
        if cls.currently_downloading():
            import os, signal

            signals = [ signal.SIGTERM, signal.SIGINT ]
            names   = [ 'cancel',       'next' ]
            to_send = signals[names.index(sig)]
            pid     = Dict['download_current'].get('pid')

            if pid:
                return cls.signal_process(pid, to_send)

    @classmethod
    def dispatch_download(cls, should_thread = True):
        if not cls.currently_downloading():
            import thread

            try:
                download = cls.download_queue().pop(0)
            except IndexError, e:
                return

            Dict['download_current'] = download
            Dict.Save()

            def perform_download():
                downloader = Downloader(download['endpoint'],
                    environment = SSPlexEnvironment(),
                    destination = cls.plex_section_destination(download['media_hint']),
                    limit       = Prefs['download_limit']
                )
                downloader.wizard.avoid_flv = Prefs['avoid_flv_downloading']

                def store_curl_pid(dl):
                    Dict['download_current']['title'] = dl.file_name()
                    Dict['download_current']['pid']   = dl.pid
                    Dict.Save()

                def update_library(dl):
                    User.plex_section_refresh(download['media_hint'])

                def clear_download_and_dispatch(dl):
                    cls.clear_current_download()
                    cls.dispatch_download(False)

                def store_download_endpoint(dl):
                    cls.download_history().append(dl.endpoint)

                downloader.on_start(store_curl_pid)

                downloader.on_success(update_library)
                downloader.on_success(store_download_endpoint)
                downloader.on_success(clear_download_and_dispatch)

                downloader.on_error(clear_download_and_dispatch)
                downloader.download()

            if should_thread:
                thread.start_new_thread(perform_download, ())
            else:
                perform_download()

def dialog(title, message):           return ObjectContainer(header = L(str(title)), message = L(str(message)))
def confirm(otitle, ocb, **kwargs):   return popup_button(L(str(otitle)), ocb, **kwargs)
def warning(otitle, ohandle, ocb, **kwargs):
    container = ObjectContainer(header = L(str(otitle)))
    container.add(button(L(str(ohandle)), ocb, **kwargs))

    return container

def plobj(obj, otitle, cb, **kwargs):
    icon = None

    if 'icon' in kwargs:
        icon = R(kwargs['icon'])
        del kwargs['icon']

    item = obj(title = otitle, key = Callback(cb, **kwargs))
    if icon:
        item.thumb = icon

    return item

def button(otitle, ocb, **kwargs):       return plobj(DirectoryObject,      L(str(otitle)), ocb, **kwargs)
def popup_button(otitle, ocb, **kwargs): return plobj(PopupDirectoryObject, L(str(otitle)), ocb, **kwargs)
def input_button(otitle, prompt, ocb, **kwargs):
    item        = plobj(InputDirectoryObject, L(str(otitle)), ocb, **kwargs)
    item.prompt = L(str(prompt))
    return item

def dispatch_download_threaded():
    User.dispatch_download()

def add_refresh_to(container, refresh, ocb, **kwargs):
    refresh           = int(refresh)
    kwargs['refresh'] = refresh + 1
    kwargs['icon']    = 'icon-refresh.png'

    if 0 < refresh:
        container.replace_parent = True

    container.add(button('heading.refresh', ocb, **kwargs))

    return container
