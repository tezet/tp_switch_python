import tornado.ioloop
import tornado.web
import os.path
from tornado.options import define, options
from tornado.escape import json_encode
from scheduller import Scheduller

import multiprocessing
import serialProcess
from rcswitch import *
from backend import *

STATE_NORMAL = 0
STATE_LEARN  = 1

MSG_OP_MCU   = 0
MSG_OP_SCHED = 1

define("port", default=8080, help="run on the given port", type=int)

class AsyncQueue:

    REASON_RC    = 0
    REASON_LEARN = 1
    REASON_MAX   = 2

    def __init__(self):
        self.waiters = []
        for i in range(self.REASON_MAX):
            self.waiters.append(set())

    def wait(self, client, reason):
        self.waiters[reason].add(client)

    def refresh_state(self, reason, arg=None):
        for waiter in self.waiters[reason]:
            waiter(arg)

        self.waiters[reason] = set()

    def cancel_wait(self, client, reason):
        self.waiters[reason].remove(client)

class Application(tornado.web.Application):

    def __init__(self, q_from_mcu, q_to_mcu, sched):

        self.aq = AsyncQueue()
        self.rc = RCSwitch(self.send_msg_to_mcu, self.aq)
        self.backend = Backend()
        self.q_from_mcu = q_from_mcu
        self.q_to_mcu = q_to_mcu
        self.sched = sched

        arguments = dict(backend=self.backend, aq=self.aq, rc=self.rc, sched=self.sched)

        handlers = [
            (r"/login", LoginHandler, arguments),
            (r"/logout", LogoutHandler, arguments),
            (r"/changepass", ChangePassHandler, arguments),
            (r"/switch", SwitchHandler, arguments),
            (r"/", SwitchList, arguments),
            (r"/edit", EditView, arguments),
            (r"/edithandler", EditHandler, arguments),
            (r"/timers", TimersView, arguments),
            (r"/timersedit", TimersEdit, arguments),
            (r"/getstate", SwitchesState, arguments),
            (r"/api/set", ApiSetHandler, arguments),
            (r"/api/get", ApiGetHandler, arguments),
            (r"/api/edit", ApiViewHandler, arguments),
            ]

        settings = {
            "static_path": os.path.join(os.path.dirname(__file__), "static"),
            "cookie_secret": "k102nxrw8oh0WCaR4qEv",
            "login_url": "/login",
            "ui_modules": {"Toggles": TogglesModule},
            "debug": True,
            "state": STATE_NORMAL
            }

        tornado.web.Application.__init__(self, handlers = handlers, **settings)

    def send_msg_to_mcu(self, msg):
        print('Sending msg to mcu: ' + msg)
        self.q_to_mcu.put(msg)

    def process_msg(self):
        if not self.q_from_mcu.empty():
            msg = self.q_from_mcu.get()

            if msg['op'] == MSG_OP_MCU:
                self.process_mcu_msg(msg['msg'])

            if msg['op'] == MSG_OP_SCHED:
                self.process_sched_msg(msg['msg'])

    def process_mcu_msg(self, msg):
        print('Received msg from mcu: ' + msg)
        if self.settings["state"] == STATE_NORMAL:
            self.rc.process_received_cmd(msg)
        elif self.settings["state"] == STATE_LEARN:
            if msg.find("[R]") <> -1:
                self.aq.refresh_state(self.aq.REASON_LEARN, msg)

    def process_sched_msg(self, msg):
        switch = self.rc.get_switch_id_by_name(msg['switch_name'])
        if switch <> None:
            state = msg['state']

            print('Received sched msg: ' + str(switch) + ':' + str(state))
            current_state = self.rc.get_state_by_id(switch)
            #toggle
            if state == 2:
                state = not current_state
                self.rc.set_switch(switch, state)
            else:
                if state <> current_state:
                    self.rc.set_switch(switch, state)


class BaseHandler(tornado.web.RequestHandler):

    def initialize(self, backend, aq, rc, sched):
        self.backend = backend
        self.aq = aq
        self.rc = rc
        self.sched = sched

        self.disable_cache()

    def disable_cache(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')

    def get_current_user(self):
        return self.get_secure_cookie("user")

class LoginHandler(BaseHandler):
    def get(self):
        alert = self.get_argument("alert", None)
        text = self.get_argument("text", None)

        creation = not self.backend.is_password_set()

        if creation:
            alert = ""
            text = self.locale.translate("This is first time you log in, create new password.")
        self.render("templates/login.html", title=self.locale.translate("User login"), alert=dict(type=alert, text=text), creation=creation)

    def post(self):
        creation = not self.backend.is_password_set()

        if creation:
            password     = self.get_argument("password")
            password_ver = self.get_argument("password_ver")
            error = False

            if password <> password_ver:
                text = self.locale.translate("Passwords were not the same.")
                error = True
            elif password == "":
                text = self.locale.translate("Password cannot be empty")
                error = True

            if error:
                alert = "danger"
                self.render("templates/login.html", title=self.locale.translate("User login"), alert=dict(type=alert, text=text), creation=creation)

            else:
                self.backend.set_password(password)
                self.redirect("/")

        else:
            if self.backend.verify_password(self.get_argument("password")):
                self.set_secure_cookie("user", "admin")
                self.redirect("/")
            else:
                alert = "danger"
                text = self.locale.translate("Incorrect password")
                self.render("templates/login.html", title="User login", alert=dict(type=alert, text=text), creation=creation)


class LogoutHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        alert = "success"
        text = self.locale.translate("You are now logged out")
        self.clear_cookie("user")
        self.render("templates/alert.html", title=self.locale.translate("Logout"), alert=dict(type=alert, text=text))

class ChangePassHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        alert = self.get_argument("alert", None)
        text = self.get_argument("text", None)
        self.render("templates/passwd.html", title=self.locale.translate("Change password"), alert=dict(type=alert, text=text))

    @tornado.web.authenticated
    def post(self):

        password_old = self.get_argument("password_old")
        password     = self.get_argument("password")
        password_ver = self.get_argument("password_ver")

        redirect = False

        if self.backend.verify_password(password_old):
            if password == password_ver:
                self.backend.set_password(password)
                alert = "success"
                text = self.locale.translate("Password changed")
            else:
                alert = "danger"
                text = self.locale.translate("New password mismatch")
                redirect = True
        else:
            alert = "danger"
            text = self.locale.translate("Incorrect password")
            redirect = True

        if redirect:
            self.redirect("/changepass?alert="+alert+"&&text="+text)
        else:
            self.render("templates/alert.html", title=self.locale.translate("Change password"), alert=dict(type=alert, text=text))

class EditView(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        alert = self.get_argument("alert", None)
        text = self.get_argument("text", None)
        self.render("templates/edit.html", title=self.locale.translate("Edit switches"), switches=self.rc.get_switches(), alert=dict(type=alert, text=text))

class EditHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        op = self.get_argument("op", None)

        if op == "edit":
            states = self.get_arguments("state", None)
            names  = self.get_arguments("name",  None)
            ons    = self.get_arguments("on",    None)
            offs   = self.get_arguments("off",   None)
            on_rets  = self.get_arguments("on_ret",    None)
            off_rets = self.get_arguments("off_ret",   None)
            counters = self.get_arguments("counter",   None)
            last_cmd_times = self.get_arguments("last_cmd_time",   None)

            switches = []
            for id in range(len(names)):
                switches.append(dict(state=states[id], on=ons[id], off=offs[id], name=names[id], on_ret=int(on_rets[id]), off_ret=int(off_rets[id]), counter=int(counters[id]) ))

            self.rc.update_db(switches)
            text = self.locale.translate("New settings saved")
            self.redirect("/edit?alert=success&&text="+text)

        elif op == "add_finish":
            on = self.get_argument("on", None)
            off = self.get_argument("off", None)
            name = self.get_argument("name", None)
            on_ret  = self.get_argument("on_ret",    None)
            off_ret = self.get_argument("off_ret",   None)
            counter = self.get_argument("counter",   None)

            self.rc.append_db(dict(state=0, on=on, off=off, name=name, on_ret=int(on_ret), off_ret=int(off_ret), counter=int(counter)))
            text = self.locale.translate("New switch has been added")
            self.redirect("/edit?alert=success&&text="+text)

    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        op = self.get_argument("op", None)
        id = self.get_argument("id", None)

        if id <> None:
            id = int(id)

        if op == "remove":
            if id <> None:
                self.rc.remove(id)
                text = self.locale.translate("Switch has been removed")
                self.redirect("/edit?alert=success&&text="+text)
        elif op == "up":
            if id <> None:
                self.rc.move_up(id)
                self.redirect("/edit")
        elif op == "down":
            if id <> None:
                self.rc.move_down(id)
                self.redirect("/edit")
        elif op == "learn_on":
            self.settings["state"] = STATE_LEARN
            self.aq.wait(self.finish_request_on, self.aq.REASON_LEARN)
        elif op == "learn_off":
            self.settings["state"] = STATE_LEARN
            self.aq.wait(self.finish_request_off, self.aq.REASON_LEARN)
        elif op == "learn_cancel":
            self.settings["state"] = STATE_NORMAL
            self.write(json_encode('OK'))
            self.finish()
        else:
            self.finish()

    def on_connection_close(self):
        self.settings["state"] = STATE_NORMAL
        self.aq.cancel_wait(self.finish_request, self.aq.REASON_LEARN)
        print('EditHandler: connection closed')

    def finish_request_on(self, cmd=None):
        cmd = cmd.replace("[R]", "").strip()
        self.settings["state"] = STATE_NORMAL
        self.write(json_encode(cmd))
        self.finish()

    def finish_request_off(self, cmd=None):
        cmd = cmd.replace("[R]", "").strip()
        self.settings["state"] = STATE_NORMAL
        self.write(json_encode(cmd))
        self.finish()


class TimersView(BaseHandler):
    @tornado.web.authenticated
    def get(self):

        def is_selected(switch_name, timer_name):
            if switch_name == timer_name:
                return "selected"
            else:
                return ""

        alert = self.get_argument("alert", None)
        text = self.get_argument("text", None)

        self.render("templates/timers.html", title=self.locale.translate("Timers"), switches=self.rc.get_switches(), timers=self.sched.get_timers(), is_selected=is_selected, alert=dict(type=alert, text=text))

class TimersEdit(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        op = self.get_argument("op", None)
        if op == "edit":
            crons    = self.get_arguments("cron", None)
            states   = self.get_arguments("state", None)
            switches = self.get_arguments("switch", None)

            if crons:
                print(crons)
            if states:
                print(states)
            if switches:
                print(switches)

            timers = []
            for id in range(len(crons)):
                timers.append(dict(cron=crons[id], state=int(states[id]), switch_name=switches[id]))
                #self.write(timer)

            self.sched.update_db(timers)
            text = self.locale.translate("New timer settings saved")
            self.redirect("/timers?alert=success&&text="+text)

        elif op == "add":
            cron    = self.get_argument("cron", None)
            state   = self.get_argument("state", None)
            switch_name = self.get_argument("switch", None)
            self.sched.append_db(dict(cron=cron, state=int(state), switch_name=switch_name))
            self.redirect("/timers")

    @tornado.web.authenticated
    def get(self):
        op = self.get_argument("op", None)
        id = self.get_argument("id", None)

        if op == "remove":
            if id <> None:
                self.sched.remove(int(id))
                self.redirect("/timers")

class SwitchList(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("templates/switches.html", title=self.locale.translate("Switches"), switches=self.rc.get_switches())


class SwitchHandler(BaseHandler):
    def switch_state(self):
        switch = self.get_argument("switch")
        switch = int(switch.replace("switch", "").strip())
        state = int(self.get_argument("state"))

        current_state = self.rc.get_state_by_id(switch)
        if state <> current_state:
            self.rc.set_switch(switch, state)

        self.write('OK')

    @tornado.web.authenticated
    def get(self):
        self.switch_state()

    @tornado.web.authenticated
    def post(self):
        self.switch_state()


class ApiSetHandler(BaseHandler):
    def get(self):
        switch = self.get_argument("switch")
        switch = int(switch.replace("switch", "").strip())
        state = int(self.get_argument("state"))
        key = self.get_argument("key")

        if self.backend.verify_key(key):
            current_state = self.rc.get_state_by_id(switch)
            if state == 2: #toggle
                state = not current_state
                self.rc.set_switch(switch, state)
            else:
                if state <> current_state:
                    self.rc.set_switch(switch, state)
            self.write('OK')
        else:
            self.write('ERROR:KEY')

class ApiGetHandler(BaseHandler):
    def get(self):
        switch = self.get_argument("switch")
        switch = int(switch.replace("switch", "").strip())
        key = self.get_argument("key")

        if self.backend.verify_key(key):
            current_state = self.rc.get_state_by_id(switch)
            self.write(str(current_state))
        else:
            self.write('ERROR:KEY')

class ApiViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        alert = self.get_argument("alert", None)
        text = self.get_argument("text", None)

        creation = not self.backend.is_key_set()
        key = self.backend.get_key()
        if key == None:
            key = ""

        if creation:
            alert = ""
            text = self.locale.translate("API access key wasn't created.")
        self.render("templates/api.html", title=self.locale.translate("API access"), alert=dict(type=alert, text=text), key=key)

    @tornado.web.authenticated
    def post(self):
        key = self.get_argument("key", None)

        if key <> None:
            alert = "success"
            text  = self.locale.translate("API key changed")
            self.backend.set_key(key)
        else:
            alert = "danger"
            text  = self.locale.translate("API key is not set")
            key = ""

        self.render("templates/api.html", title=self.locale.translate("API access"), alert=dict(type=alert, text=text), key=key)


class SwitchesState(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        self.aq.wait(self.finish_request, self.aq.REASON_RC)

    def on_connection_close(self):
        self.aq.cancel_wait(self.finish_request, self.aq.REASON_RC)
        print('SwitchesState: connection closed')

    def finish_request(self, arg=None):
        switches = []
        for switch_id in range(self.rc.get_switches_len()):
            switches.append({str(switch_id) : self.rc.get_state_by_id(switch_id)})
        print('Update state:')
        print(switches)
        self.write(json_encode(switches))
        self.finish()

class TogglesModule(tornado.web.UIModule):
    def render(self, switch, id):
        return self.render_string("modules/toggles.html", switch=switch, id=id)

    def javascript_files(self):
        return {"js/toggles.min.js"}

    def css_files(self):
        return "css/toggles-light.css"


def main():

    tornado.options.parse_command_line()
    q_to_mcu = multiprocessing.Queue()
    q_from_mcu = multiprocessing.Queue()

    def my_job(arg):
        print('Running sched job')
        q_from_mcu.put(dict(op=MSG_OP_SCHED, msg=arg))

    sched = Scheduller(my_job)

    sp = serialProcess.SerialProcess(q_to_mcu, q_from_mcu, MSG_OP_MCU)
    sp.daemon = True
    sp.start()
    q_to_mcu.put("ping")

    tornado.locale.load_translations(os.path.join(os.path.dirname(__file__), "translations"))

    app = Application(q_from_mcu, q_to_mcu, sched)
    app.listen(options.port)
    print "Listening on port:", options.port

    mainLoop = tornado.ioloop.IOLoop.instance()
    scheduler = tornado.ioloop.PeriodicCallback(app.process_msg, 10, io_loop = mainLoop)

    scheduler.start()
    mainLoop.start()


if __name__ == "__main__":
    main()

