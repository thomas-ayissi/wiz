from season.core.component.base.workspace import Workspace as Base, App as AppBase
from season.core.component.base.workspace import build_cmd, localized, ESBUILD_SCRIPT, ENV_SCRIPT

import season
import os
import json
import datetime
import re
from werkzeug.routing import Map, Rule

def build_default_init(workspace, config):
    rootfs = workspace.fs()
    srcfs = workspace.fs("src")

    working_dir = rootfs.abspath()
    build_folder = workspace.build.folder()
    build_dir = os.path.join(working_dir, build_folder)

    if rootfs.exists(build_folder):
        return

    build_cmd(workspace, f'cd {working_dir} && {config.command_ng} new {build_folder} --routing true --style scss --interactive false  --skip-tests true --skip-git true')    
    
    fs = workspace.fs(build_dir)
    fs.write('wizbuild.js', ESBUILD_SCRIPT)
    fs.write(os.path.join('src', 'environments', 'environment.ts'), ENV_SCRIPT)

    if srcfs.isfile(os.path.join("angular", "package.json")):
        fs.copy(srcfs.abspath(os.path.join("angular", "package.json")), "package.json")
        build_cmd(workspace, f"cd {build_dir} && npm install")

    build_cmd(workspace, f"cd {build_dir} && npm install ngc-esbuild pug jquery socket.io-client --save")

def build_default(workspace, filepath):
    def convert_to_class(value):
        app_id_split = value.split(".")
        componentname = []
        for wsappname in app_id_split:
            componentname.append(wsappname.capitalize())
        componentname = "".join(componentname)
        return componentname

    srcfs = workspace.fs("src")
    distfs = workspace.fs("dist")
    buildfs = workspace.build.fs()
    build_folder = workspace.build.folder()
    pugfiles = []

    if len(filepath) == 0:
        buildfs.delete("src/app")
        buildfs.delete("src/service")

    # build file and pug cache
    def build_file(target_file):
        target_file_split = target_file.split("/")
        target_folder = ['angular', 'app', '']
        target = target_file_split[0]
        if target not in target_folder:
            return

        if srcfs.exists(target_file) == False:
            srcfs.delete(target_file)
            return

        if srcfs.isdir(target_file):
            files = srcfs.files(target_file)
            for file in files:
                build_file(os.path.join(target_file, file))
            return
        
        extension = os.path.splitext(target_file)[-1]

        # catch pug files
        if extension == '.pug':
            pugbuildpath = srcfs.abspath(target_file[:-len(extension)])
            pugfiles.append(pugbuildpath)
            return

        # if app src
        if target == 'app':
            copyfile = os.path.join("src", target_file)
            copyfolder = os.path.dirname(copyfile)
            if buildfs.isdir(copyfolder) == False:
                buildfs.makedirs(copyfolder)

            if extension == ".ts":
                app_id = target_file_split[1]
                app_id_split = app_id.split(".")

                filename = app_id + ".component"

                componentname = []
                for wsappname in app_id_split:
                    componentname.append(wsappname.capitalize())
                componentname = "".join(componentname)

                code = srcfs.read(target_file)
                appjson = srcfs.read.json(os.path.join(os.path.dirname(target_file), "app.json"), dict())
                
                importstr = "import { Component, OnInit } from '@angular/core';\n"
                implements = 'OnInit'
                if 'ng.implements' in appjson:
                    implements = appjson['ng.implements']
                if len(implements) < 3:
                    implements = "OnInit"

                if implements != 'OnInit':
                    implementsarr = implements.split(".")
                    implementsfilename = implementsarr[-1] + ".component"
                    implementscomp = []
                    for wsappname in implementsarr:
                        implementscomp.append(wsappname.capitalize())
                    implementscomp = "".join(implementscomp) + "Component"
                    implementsfrom = "../".join(['' for x in range(len(app_id_split) + 1)]) + implements + "/" + implementsfilename
                    importstr = f"{importstr}import {implementscomp} from '{implementsfrom}';\n"
                else:
                    implementscomp = implements

                def replace_import_service(value):
                    pattern = r'@wiz.service\((\S+)\)'
                    def convert(match_obj):
                        val = match_obj.group(1)
                        return f'src/service/{val}'
                    return re.sub(pattern, convert, value)

                def replace_import_app(value):
                    pattern = r'@wiz.app\((\S+)\)'
                    def convert(match_obj):
                        val = match_obj.group(1)
                        return f'src/app/{val}/{val}.component'
                    return re.sub(pattern, convert, value)

                code = replace_import_service(code)
                code = replace_import_app(code)

                code = code.replace('export class Component', "@Component({\n    selector: 'wiz-" + "-".join(app_id_split) + "',\n    templateUrl: './view.html',\n    styleUrls: ['./view.scss']\n})\n" + f'export class {componentname}Component implements {implementscomp}')
                code = f"{importstr}\n" + code.strip()

                wizts = srcfs.read(os.path.join("angular", "wiz.ts")).replace("@wiz.namespace", app_id)
                wizts = wizts.replace("@wiz.baseuri", workspace.wiz.server.config.service.wizurl)
                code = wizts + code

                copyfile = os.path.join(copyfolder, filename + ".ts")                
                buildfs.write(copyfile, code)

                appjson["ng.build"] = dict(id=app_id, name=componentname + "Component", path="./" + app_id + "/" + filename)
                srcfs.write(os.path.join(os.path.dirname(target_file), "app.json"), json.dumps(appjson, indent=4))
            else:
                buildfs.copy(srcfs.abspath(target_file), copyfile)
        
        elif target == 'angular':
            ngtarget = target_file_split[1]
            ngfilepath = os.path.join(*target_file.split("/")[1:])

            copyfile = os.path.join("src", ngfilepath)
            copyfolder = os.path.dirname(copyfile)
            if buildfs.isdir(copyfolder) == False:
                buildfs.makedirs(copyfolder)

            if ngtarget == 'service':
                code = srcfs.read(target_file)
                code = code.replace("export class", "import { Injectable } from '@angular/core';\n@Injectable({ providedIn: 'root' })\nexport class")
                buildfs.write(copyfile, code)

            if ngtarget == 'styles':
                ngfilepath = os.path.join(*target_file.split("/")[2:])
                copyfile = os.path.join("src", ngfilepath)
                buildfs.write(copyfile, srcfs.read(target_file))

            elif ngtarget == 'angular.build.options.json':
                ng_build_options = srcfs.read.json(target_file)
                angularjson = buildfs.read.json("angular.json", dict())
                for key in ng_build_options:
                    if key in ["outputPath", "index", "main", "polyfills", "tsConfig", "inlineStyleLanguage"]: continue
                    angularjson["projects"][build_folder]["architect"]["build"]["options"][key] = ng_build_options[key]
                buildfs.write("angular.json", json.dumps(angularjson, indent=4))

            elif ngtarget in ['app', 'index.html']:
                buildfs.copy(srcfs.abspath(target_file), copyfile)

    build_file(filepath)
        
    # compile pug files as bulk
    pugfilepaths = " ".join(pugfiles)
    cmd = f"cd {buildfs.abspath()} && node wizbuild {pugfilepaths}"
    build_cmd(workspace, cmd)

    for pugfile in pugfiles:
        pugfile = pugfile[len(srcfs.abspath()) + 1:]
        target = pugfile.split("/")[0]
        htmlfile = pugfile + ".html"
        
        if target == 'app':
            copyfile = os.path.join("src", pugfile + ".html")
            copyfolder = os.path.dirname(copyfile)
            if buildfs.isdir(copyfolder) == False:
                buildfs.makedirs(copyfolder)
            buildfs.copy(srcfs.abspath(htmlfile), copyfile)

        elif htmlfile == 'angular/index.html':
            copyfile = os.path.join("src", "index.html")
            buildfs.copy(srcfs.abspath(htmlfile), copyfile)

        elif htmlfile == 'angular/app/app.component.html':
            copyfile = os.path.join("src", "app", "app.component.html")
            buildfs.copy(srcfs.abspath(htmlfile), copyfile)

    # load apps
    apps = workspace.app.list()
    appsmap = dict()
    _apps = []
    for app in apps:
        try:
            _apps.append(app['ng.build'])
            appsmap[app['id']] = app['ng.build']
        except Exception as e:
            pass
    apps = _apps

    component_import = "\n".join(["import { " + x['name'] + " } from '" + x['path'] + "';" for x in apps])
    component_declarations = "AppComponent,\n" + ",\n".join(["        " + x['name'] for x in apps])
    
    # auto build: app.module.ts
    app_module_ts = srcfs.read(os.path.join("angular", "app", "app.module.ts"))
    app_module_ts = app_module_ts.replace("'@wiz.declarations'", component_declarations).replace('"@wiz.declarations"', component_declarations)
    app_module_ts = component_import + "\n\n" + app_module_ts
    buildfs.write(os.path.join("src", "app", "app.module.ts"), app_module_ts)

    # auto build: app-routing.modules.ts
    app_routing_opt = srcfs.read(os.path.join("angular", "app", "app-routing.module.ts"))
    
    def replace_import_app(value):
        pattern = r'\'@wiz.app\((\S+)\)\''
        def convert1(match_obj):
            val = match_obj.group(1).replace(" ", "")
            cname = convert_to_class(val)
            return cname + "Component"
        value = re.sub(pattern, convert1, value)

        pattern = r'\"@wiz.app\((\S+)\)\"'
        def convert2(match_obj):
            val = match_obj.group(1).replace(" ", "")
            cname = convert_to_class(val)
            return cname + "Component"
        return re.sub(pattern, convert2, value)

    app_routing_opt = replace_import_app(app_routing_opt)

    app_routing_ts = "import { NgModule } from '@angular/core';\nimport { RouterModule, Routes } from '@angular/router';\n"
    app_routing_ts = app_routing_ts + "\n" + component_import
    app_routing_ts = app_routing_ts + "\n\n" + "const routes: Routes = " + app_routing_opt
    app_routing_ts = app_routing_ts + "\n\n" + "@NgModule({ imports: [RouterModule.forRoot(routes)], exports: [RouterModule] })"
    app_routing_ts = app_routing_ts + "\n" + "export class AppRoutingModule { }"
    buildfs.write(os.path.join("src", "app", "app-routing.module.ts"), app_routing_ts)

    # run esbuild
    cmd = f"cd {workspace.build.path()} && node wizbuild"
    build_cmd(workspace, cmd)

    # copy to dist
    if distfs.isdir(): distfs.delete()
    srcfs.copy(buildfs.abspath(os.path.join("dist", build_folder)), distfs.abspath())
    srcfs.copy(buildfs.abspath("package.json"), os.path.join("angular", "package.json"))

class Build:
    def __init__(self, workspace):
        self.workspace = workspace

    def folder(self):
        workspace = self.workspace
        wiz = workspace.wiz
        config = wiz.server.config.build
        return config.folder
    
    def fs(self, *args):
        return self.workspace.fs(self.folder())

    def path(self, *args):
        return self.fs().abspath()

    def init(self):
        workspace = self.workspace
        wiz = workspace.wiz
        config = wiz.server.config.build

        fn = build_default_init
        if config.init is not None:
            fn = config.init

        season.util.fn.call(fn, wiz=wiz, workspace=workspace, season=season, config=config)

    def clean(self):
        workspace = self.workspace
        wiz = workspace.wiz
        config = wiz.server.config.build
        
        fs = self.fs()
        if fs.exists():
            fs.delete()

        self.init()

    def __call__(self, filepath=None):
        workspace = self.workspace
        wiz = workspace.wiz
        config = wiz.server.config.build

        fn = build_default
        if config.build is not None:
            fn = config.build

        srcfs = workspace.fs("src").abspath()
        if filepath is None:
            filepath = ""
        elif filepath.startswith(srcfs):
            filepath = filepath[len(srcfs):]
            if len(filepath) > 0 and filepath[0] == "/":
                filepath = filepath[1:]

        season.util.fn.call(fn, wiz=wiz, workspace=workspace, season=season, config=config, filepath=filepath)
        workspace.route.build()

class Route:
    def __init__(self, workspace):
        self.workspace = workspace
        self.wiz = workspace.wiz
        self.id  = None
    
    def list(self):
        fs = self.workspace.fs("src", "route")
        routes = fs.files()
        res = []
        for id in routes:
            route = self(id).data(code=False)
            if route is None:
                continue
            res.append(route['package'])
        res.sort(key=lambda x: x['id'])
        return res

    def build(self):
        url_map = []
        rows = self.list()
        routes = []
        for row in rows:
            obj = dict()
            obj['route'] = row['route']
            obj['id'] = row['id']
            routes.append(obj)
        
        for i in range(len(routes)):
            info = routes[i]
            route = info['route']
            if route is None: continue
            if len(route) == 0: continue

            endpoint = info["id"]
            if route == "/":
                url_map.append(Rule(route, endpoint=endpoint))
                continue
            if route[-1] == "/":
                url_map.append(Rule(route[:-1], endpoint=endpoint))
            elif route[-1] == ">":
                rpath = route
                while rpath[-1] == ">":
                    rpath = rpath.split("/")[:-1]
                    rpath = "/".join(rpath)
                    url_map.append(Rule(rpath, endpoint=endpoint))
                    if rpath[-1] != ">":
                        url_map.append(Rule(rpath + "/", endpoint=endpoint))
            url_map.append(Rule(route, endpoint=endpoint))

        fs = self.workspace.fs("cache")
        fs.write.pickle("urlmap", url_map)
        return url_map

    def match(self, uri):
        if len(uri) > 1 and uri[-1] == "/": uri = uri[:-1]

        fs = self.workspace.fs("cache")
        urlmap = fs.read.pickle("urlmap", None)
        if urlmap is None:
            urlmap = self.build()
        
        urlmap = Map(urlmap)
        urlmap = urlmap.bind("", "/")

        def matcher(url):
            try:
                endpoint, kwargs = urlmap.match(url, "GET")
                return endpoint, kwargs
            except:
                return None, {}
        
        id, segment = matcher(uri)
        return self(id), segment

    def is_instance(self):
        return self.id is not None

    def __call__(self, id):
        if id is None: return self
        id = id.lower()
        route = Route(self.workspace)
        route.id = id
        return route

    @localized
    def proceed(self):
        wiz = self.wiz
        app_id = self.id
        data = self.data()

        if data is None:
            return
        
        ctrl = None
        
        if 'controller' in data['package'] and len(data['package']['controller']) > 0:
            ctrl = data['package']['controller']
            ctrl = self.workspace.controller(ctrl)

        tag = wiz.mode()
        logger = wiz.logger(f"[{tag}/route/{app_id}]")
        dic = self.dic()

        name = self.fs().abspath('controller.py')
        season.util.os.compiler(data['controller'], name=name, logger=logger, controller=ctrl, dic=dic, wiz=wiz)

    @localized
    def fs(self, *args):
        return self.workspace.fs('src', 'route', self.id, *args)

    @localized
    def dic(self, lang=None):
        APP_ID = self.id
        wiz = self.wiz
        fs = self.fs("dic")

        if lang is None:
            lang = wiz.request.language()
            lang = lang.lower()
        
        data = fs.read.json(f'{lang}.json', None)
        if data is None:
            data = fs.read.json("default.json", dict())
        
        class Loader:
            def __init__(self, dicdata):
                self.dicdata = dicdata

            def __call__(self, key=None):
                dicdata = self.dicdata
                if key is None: 
                    return season.util.std.stdClass(dicdata)
                
                key = key.split(".")
                tmp = dicdata
                for k in key:
                    if k not in tmp:
                        return ""
                    tmp = tmp[k]
                return tmp

        return Loader(data)

    @localized
    def data(self, code=True):
        APP_ID = self.id
        wiz = self.wiz
        fs = self.fs()

        pkg = dict()
        pkg['package'] = fs.read.json('app.json', None)
        if pkg['package'] is None:
            return None

        pkg['package']['id'] = APP_ID
        
        def readfile(key, filename, default=""):
            try: 
                pkg[key] = fs.read(filename)
            except: 
                pkg[key] = default
            return pkg
        
        if code:
            pkg = readfile("controller", "controller.py")
            pkg['dic'] = dict()
            if fs.isdir("dic"):
                dics = fs.files("dic")
                for dic in dics:
                    try:
                        lang = os.path.splitext(dic)[0]
                        lang = lang.lower()
                        pkg['dic'][lang] = fs.read(os.path.join("dic", dic), '{}')
                    except:
                        pass

        return pkg

    @localized
    def update(self, data):
        required = ['package', 'dic', 'controller']
        for key in required:
            if key not in data: 
                raise Exception(f"'`{key}`' not defined")

        for key in data:
            if type(data[key]) == str:
                data[key] = data[key].replace('', '')

        data['package']['id'] = self.id

        if len(data['package']['id']) < 3:
            raise Exception(f"id length at least 3")
        
        allowed = "qwertyuiopasdfghjklzxcvbnm.1234567890"
        for c in data['package']['id']:
            if c not in allowed:
                raise Exception(f"only alphabet and number and . in package id")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if 'created' not in data['package']:
            data['package']['created'] = timestamp

        fs = self.fs()
        fs.write.json("app.json", data['package'])
        fs.write("controller.py", data['controller'])
        
        if fs.isdir("dic"):
            fs.delete("dic")
        fs.makedirs("dic")
        dicdata = data['dic']
        for lang in dicdata:
            val = dicdata[lang]
            lang = lang.lower()
            fs.write(os.path.join("dic", lang + ".json"), val)

        self.build()

    @localized
    def delete(self):
        self.fs().delete()
        self.build()

class App(AppBase):
    def __init__(self, workspace):
        super().__init__(workspace)

    def __call__(self, app_id):
        if app_id is None: return self
        app_id = app_id.lower()
        app = App(self.workspace)
        app.id = app_id
        return app

    def list(self):
        fs = self.workspace.fs('src', 'app')
        apps = fs.files()
        res = []
        for app_id in apps:
            app = self(app_id).data(code=False)
            if app is None:
                continue
            res.append(app['package'])
        res.sort(key=lambda x: x['id'])
        return res

    @localized
    def fs(self, *args):
        return self.workspace.fs('src', 'app', self.id, *args)

    @localized
    def data(self, code=True):
        APP_ID = self.id
        wiz = self.wiz
        fs = self.fs()

        pkg = dict()
        pkg['package'] = fs.read.json('app.json', None)
        if pkg['package'] is None:
            return None

        pkg['package']['id'] = APP_ID
        
        viewtype = 'pug'
        if 'viewtype' in pkg['package']:
            viewtype = pkg['package']['viewtype']
        if viewtype not in ['pug', 'html']:
            viewtype = 'pug'

        def readfile(key, filename, default=""):
            try: 
                pkg[key] = fs.read(filename)
            except: 
                pkg[key] = default
            return pkg
        
        if code:
            pkg = readfile("api", "api.py")
            pkg = readfile("socketio", "socketio.py")
            pkg = readfile("view", f"view.{viewtype}")
            pkg = readfile("typescript", f"view.ts")
            pkg = readfile("scss", f"view.scss")

            pkg['dic'] = dict()
            if fs.isdir("dic"):
                dics = fs.files("dic")
                for dic in dics:
                    try:
                        lang = os.path.splitext(dic)[0]
                        lang = lang.lower()
                        pkg['dic'][lang] = fs.read(os.path.join("dic", dic), '{}')
                    except:
                        pass

        return pkg

    def before_update(self, data):
        required = ['package', 'dic', 'api', 'socketio', 'view', 'typescript', 'scss']
        for key in required:
            if key not in data: 
                raise Exception(f"'`{key}`' not defined")

        data['package']['id'] = self.id
        if len(data['package']['id']) < 3:
            raise Exception(f"id length at least 3")

        allowed = "qwertyuiopasdfghjklzxcvbnm.1234567890"
        for c in data['package']['id']:
            if c not in allowed:
                raise Exception(f"only alphabet and number and . in package id")

        return data

    def do_update(self, data):
        viewtype = 'pug'
        if 'viewtype' in data['package']:
            viewtype = data['package']['viewtype']
        if viewtype not in ['pug', 'html']:
            viewtype = 'pug'

        fs = self.fs()
        fs.write("api.py", data['api'])
        fs.write("socketio.py", data['socketio'])
        fs.write(f"view.{viewtype}", data['view'])
        fs.write("view.ts", data['typescript'])
        fs.write("view.scss", data['scss'])

class Workspace(Base):
    def __init__(self, wiz):
        super().__init__(wiz)
        self.build = Build(self)
        self.app = App(self)
        self.route = Route(self)

    def path(self, *args):
        return self.wiz.branch.path(*args)
    
    def controller(self, namespace):
        wiz = self.wiz
        fs = self.fs("src", "controller")
        code = fs.read(f"{namespace}.py")
        logger = wiz.logger(f"[ctrl/{namespace}]")
        ctrl = season.util.os.compiler(code, name=fs.abspath(namespace + ".py"), logger=logger, wiz=wiz)
        return ctrl['Controller']
    
    def model(self, namespace):
        wiz = self.wiz
        fs = self.fs("src", "model")
        code = fs.read(f"{namespace}.py")
        logger = wiz.logger(f"[model/{namespace}]")
        model = season.util.os.compiler(code, name=fs.abspath(namespace + ".py"), logger=logger, wiz=wiz)
        return model['Model']