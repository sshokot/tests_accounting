from odoo import api, models, fields
from odoo.exceptions import ValidationError
import re, datetime
from pytz import timezone, UTC

class TestTags(models.Model):
    _name = 'tests.accounting.tag'
    _description = 'Tags for tests accounting'

    name = fields.Char()


class Tester(models.Model):
    _name = 'tests.accounting.tester'
    _description = 'model of tester for tests accounting'

    name = fields.Char()
    email = fields.Char()
    test_ids = fields.One2many('tests.accounting.test','tester_id',string='Tests')

    @api.model
    def get_available_testers(self,date_from,max_days,test_duration):
        avail_testers = []
        hour_from = date_from.hour
        if date_from.minute!=0:
            hour_from +=1
        start_day = date_from.replace(hour=hour_from)

        finish_day = start_day + datetime.timedelta(days=max_days)
        finish_day = self.env['tests.accounting.test'].get_day_end_shift(finish_day)
        testers = self.env['tests.accounting.tester'].sudo().search([])
        for tester in testers:
            free_date = tester.get_free_date(start_day,test_duration)
            if start_day<=free_date<=finish_day:
                avail_testers.append(tester.id)
        return avail_testers

    @api.constrains('email')
    def validate_email(self):
        self.ensure_one()
        if self.email and not re.match('(\w+[.|\w])*@(\w+[.])*\w+', self.email):
            raise ValidationError('Wrong Email, must be *@*')

    def get_free_date(self, date_from, max_duration, tz):
        model_test = self.env['tests.accounting.test']
        shift_end = model_test.get_shift_end()
        tests_from = date_from - datetime.timedelta(hours=max_duration)
        tests = model_test.sudo().search([('tester_id','=',self.id),('expiration_date','>',tests_from)],order='date')
        start_date = date_from
        for test in tests:
            test_begin = test.date.astimezone(tz)
            test_finish = test.expiration_date.astimezone(tz)
            if test_begin.timestamp()>=start_date.timestamp():
                if (test_begin.hour - start_date.hour)>max_duration:
                     break
            start_date = test_finish
        if (shift_end - start_date.hour)<max_duration:
            new_date = start_date + datetime.timedelta(days=1)
            start_date = new_date.replace(hour=model_test.get_shift_begin())
        return model_test.get_utc_date_from_datetz(start_date, tz)


class Test(models.Model):
    _name = 'tests.accounting.test'
    _description = 'model of test for tests accounting'

    name =  fields.Char(required=True)
    description = fields.Text(required=True)
    date = fields.Datetime(string='Date and time of the test ')
    expiration_date = fields.Datetime(string='Expiration date', compute='_compute_expiration_date', store=True, readonly=True)
    tester_id = fields.Many2one('tests.accounting.tester', string='Tester')
    tag_id = fields.Many2many('tests.accounting.tag',string='Tags')
    duration = fields.Integer('Test duration (hours)', required=True)
    state = fields.Selection([('draft','Draft'),('assigned','Assigned'),('performing','Performing'),
                              ('completed','Completed')], readonly=True, default='draft')
    @api.model
    def get_utc_date_from_datetz(self, date_in_tz, tz):
        new_date = (date_in_tz - date_in_tz.utcoffset()).replace(tzinfo=tz).replace(tzinfo=None) if date_in_tz.utcoffset() else date_in_tz
        return new_date

    @api.model
    def get_shift_begin(self):
        ircp = self.env['ir.config_parameter'].sudo()
        return int(ircp.get_param('tests_accounting.work_shift_begin'))

    @api.model
    def get_shift_end(self):
        ircp = self.env['ir.config_parameter'].sudo()
        start_shift = self.get_shift_begin()
        work_time = int(ircp.get_param('tests_accounting.work_time'))
        return start_shift + work_time

    @api.model
    def get_day_end_shift(self,date):
        end_shift = self.get_shift_end()
        end_date = date.replace(hour=end_shift)
        return end_date

    @api.model
    def check_tests_state(self):
        model_ta = self.env['tests.accounting.test']
        tests = model_ta.sudo().search([('state','!=','completed')])

        for test in tests:
            right_now = datetime.datetime.now()
            if test.tester_id:
                if test.date <=right_now:
                    if test.expiration_date>right_now:
                        test.state = 'performing'
                    else:
                        test.state = 'completed'
                else:
                    test.state = 'assigned'

    @api.constrains('duration')
    def validate_duration(self):
        self.ensure_one()
        max_duration = int(self.env['ir.config_parameter'].sudo().get_param('tests_accounting.max_test_duration'))
        if self.duration > max_duration:
            raise ValidationError('Duration mast be less than %s' % max_duration)
        elif self.duration == 0:
            raise ValidationError('Duration should not be equal 0')

    @api.depends('date', 'duration')
    def _compute_expiration_date(self):
        tz = timezone(self.env.user.tz)
        for rec in self:
           if rec.date:
               add_hours = datetime.timedelta(hours=rec.duration)
               rec.date = self.check_start_date(rec.date.astimezone(tz), rec.duration, tz)
               rec.expiration_date = rec.date + add_hours

    def _set_start_expiration_dates(self):
        ircp = self.env['ir.config_parameter'].sudo()
        max_duration = int(ircp.get_param('tests_accounting.max_test_duration'))
        duration = self.duration if self.duration else max_duration
        add_hours = datetime.timedelta(hours=self.duration)
        tz = timezone(self.env.user.tz)
        start_time = datetime.datetime.utcnow().astimezone(tz)
        start_time = self.tester_id.get_free_date(start_time, duration,tz)
        bd = self.date if self.date else start_time
        new_start = self.check_start_date(bd, duration, tz)
        new_exp = new_start + add_hours
        self.date = new_start
        self.expiration_date = new_exp

    @api.onchange('tester_id','date','duration')
    def on_change_tester_id(self):
        for rec in self:
            if rec.tester_id:
                rec._set_start_expiration_dates()

    def check_start_date(self, start_date, duration, tz):
        start_shift = self.get_shift_begin()
        end_shift = self.get_shift_end()
        bd = start_date if start_date.utcoffset() else start_date.astimezone(tz)
        bd_h = bd.hour
        bd_m = bd.minute
        if bd_m!=0:
            bd_h += 1
        if (bd_h+duration)>end_shift:
            bd = bd + datetime.timedelta(hours=(24-bd.hour+start_shift))
            bd_h = bd.hour

        checked_date = bd.replace(hour=bd_h,minute=0,second=0, microsecond=0).astimezone(tz)

        return self.env['tests.accounting.test'].get_utc_date_from_datetz(checked_date, tz)



