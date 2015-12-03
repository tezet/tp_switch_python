from apscheduler.scheduler import Scheduler
import shelve
import os.path

class Scheduller():

    def __init__(self, job_func):
        self.job_func = job_func
        self.jobs = []

        config = {'apscheduler.standalone': False }
        self.sched = Scheduler(config)
        self.sched.start()

        self.db = shelve.open(os.path.join(os.path.dirname(__file__), "db/db_timers"), writeback=True)

        if not self.db.has_key('timers'):
            print('Creating new timers db')
            self.db['timers'] = []

        self.apply_all_timers(self.db['timers'])

        #self.db['timers'] = []
        #self.db['timers'].append(dict(cron="* * * * *", switch_name="TV", state=1))
        #self.db['timers'].append(dict(cron="20 14 * * *", switch_name="Speakers", state=1))
        #self.db['timers'].append(dict(cron="30 14 * * *", switch_name="Speakers", state=0))
        #self.db_flush()

    def db_flush(self):
        self.db.sync()
        self.db.close()
        self.db = shelve.open(os.path.join(os.path.dirname(__file__), "db/db_timers"), writeback=True)

    def get_timers(self):
        return self.db['timers']

    def update_db(self, timers):
        self.remove_all_jobs()
        self.db['timers'] = timers
        self.db_flush()
        self.apply_all_timers(self.db['timers'])

    def append_db(self, new_timer):
        self.db['timers'].append(new_timer)
        self.db_flush()
        self.schedulle_job(new_timer)

    def remove_all_jobs(self):
        for id, timer in enumerate(self.db['timers']):
            self.unschedule_job(id)
        self.db_flush()

    def apply_all_timers(self, timers):
        for timer in timers:
            self.schedulle_job(timer)

    def schedulle_job(self, timer):
        switch_name = timer['switch_name']
        state = timer['state']
        minute, hour, day, month, day_of_week = timer['cron'].split()

        #workaround for apscheduler, Monday is day 0 in it's implementation
        if (day_of_week<> "*"):
            day_of_week = int(day_of_week) - 1
            if (day_of_week == -1):
                day_of_week = 6

        job = self.sched.add_cron_job(self.job_func, second=0, minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, args=[dict(switch_name=switch_name, state=state)])
        self.jobs.append(job)

    def unschedule_job(self, id):
        print 'remove ID:', id
        self.db['timers'].pop(id)

        self.sched.unschedule_job(self.jobs.pop(int(id)))

    def remove(self, id):
        self.unschedule_job(id)
        self.db_flush()



