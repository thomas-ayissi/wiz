import season
import sys
import requests
import json

class Controller(season.interfaces.wiz.admin.base):

    def __startup__(self, framework):
        super().__startup__(framework)
        self.css('css/setting/main.less')
        self.js('js/setting/global.js')
        menus = []
        menus.append({"url": "/wiz/admin/setting/general_status", "icon": "fas fa-cog", "title": "General", 'pattern': r'^/wiz/admin/setting/general', "sub": [
            {"url": "/wiz/admin/setting/general_status", "icon": "fas fa-caret-right", "title": "System Status"},
            {"url": "/wiz/admin/setting/general_wiz", "icon": "fas fa-caret-right", "title": "WIZ Setting"}
        ]})
        menus.append({"url": "/wiz/admin/setting/framework_general", "icon": "fas fa-rocket", "title": "Framework", 'pattern': r'^/wiz/admin/setting/framework', "sub": [
            {"url": "/wiz/admin/setting/framework_general", "icon": "fas fa-caret-right", "title": "Settings"},
            {"url": "/wiz/admin/setting/framework_config", "icon": "fas fa-caret-right", "title": "Config Files"},
            {"url": "/wiz/admin/setting/framework_lib", "icon": "fas fa-caret-right", "title": "Library"},
            {"url": "/wiz/admin/setting/framework_dic", "icon": "fas fa-caret-right", "title": "Dictionary"}
        ]})
        menus.append({"url": "/wiz/admin/setting/deploy", "icon": "fas fa-cloud-download-alt", "title": "Deploy & Backup"})
        menus.append({"url": "/wiz/admin/setting/restore", "icon": "fas fa-history", "title": "Restore"})
        menus.append({"url": "/wiz/admin/setting/cache_status", "icon": "fas fa-file-medical-alt", "title": "Cache Status"})

        try:
            framework.response.data.set(SEASON_VERSION=season.version)
        except:
            framework.response.data.set(SEASON_VERSION="<= 0.3.8")
        framework.response.data.set(PYTHON_VERSION=sys.version)

        self.setting_nav(menus)

    def __default__(self, framework):
        framework.response.redirect('/wiz/admin/setting/general_status')


    def general_status(self, framework):
        self.js('js/setting/general/status.js')
        isupdate = False
        latest_version = "Unknown"
        try:
            packageinfo = json.loads(requests.get("https://raw.githubusercontent.com/season-framework/season-flask-wiz/main/wiz-package.json").text)
            latest_version = packageinfo['version']
            versioninfo = packageinfo['version'].split(".")
            wizversion = self.db.package.version.split(".")
            if int(wizversion[0]) < int(versioninfo[0]):
                isupdate = True
            if int(wizversion[0]) == int(versioninfo[0]):
                if int(wizversion[1]) < int(versioninfo[1]):
                    isupdate = True
                if int(wizversion[1]) == int(versioninfo[1]):
                    if int(wizversion[2]) < int(versioninfo[2]):
                        isupdate = True
        except:
            pass
        
        framework.response.render('setting/general/status.pug', is_dev=self.wiz.is_dev(), latest_version=latest_version, isupdate=isupdate)

    def general_wiz(self, framework):
        self.js('js/setting/general/wiz.js')
        self.exportjs(themes=self.db.themes())
        framework.response.render('setting/general/wiz.pug', is_dev=self.wiz.is_dev())


    # framework settings
    def framework_general(self, framework):
        self.js('js/setting/framework/setting.js')
        framework.response.render('setting/framework/setting.pug', is_dev=self.wiz.is_dev())

    def framework_config(self, framework):
        self.exportjs(target=[{"path": "app", "name": "config"}])
        self.js('js/setting/framework/config.js')
        framework.response.render('setting/framework/config.pug')

    def framework_lib(self, framework):
        self.exportjs(target=[{"path": "app", "name": "lib"}])
        self.js('js/editor.js')
        framework.response.render('setting/framework/editor.pug')

    def framework_dic(self, framework):
        self.exportjs(target=[{"path": "app", "name": "dic"}])
        self.js('js/editor.js')
        framework.response.render('setting/framework/editor.pug')

    
    def deploy(self, framework):
        self.js('js/setting/deploy.js')
        framework.response.render('setting/deploy.pug')

    def restore(self, framework):
        self.js('js/setting/restore.js')
        framework.response.render('setting/restore.pug')

    def cache_status(self, framework):
        self.js('js/setting/cache.js')
        framework.response.render('setting/cache.pug')

    def setting_nav(self, menus):
        framework = self.__framework__

        for menu in menus:
            pt = None
            if 'pattern' in menu: pt = menu['pattern']
            elif 'url' in menu: pt = menu['url']

            if pt is not None:
                if framework.request.match(pt): menu['class'] = 'active'
                else: menu['class'] = ''

            if 'sub' in menu:
                for sub in menu['sub']:
                    pt = None
                    if 'pattern' in sub: pt = sub['pattern']
                    elif 'url' in sub: pt = sub['url']

                    if pt is not None:
                        if framework.request.match(pt): sub['class'] = 'active'
                        else: sub['class'] = ''

        framework.response.data.set(settingmenus=menus)