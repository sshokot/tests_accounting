from odoo import api, models, fields
from odoo.exceptions import ValidationError
import re, datetime

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

    @api.constrains('email')
    def validate_email(self):
        self.ensure_one()
        if self.email and not re.match('(\w+[.|\w])*@(\w+[.])*\w+', self.email):
            raise ValidationError('Wrong Email, must be *@*')

    def get_free_date(self, date_from, max_duration):
        model_test = self.env['tests.accounting.test']
        shift_end = model_test.get_shift_end()
        tests = model_test.sudo().search([('tester_id','=',self.id),('expiration_date','>',date_from)],order='date')
        start_date = date_from
        for test in tests:
            test_begin = test.date
            test_finish = test.expiration_date
            if test_begin>start_date:
                if (test_begin.hour - start_date.hour)>max_duration:
                     break
            start_date = test_finish
        if (shift_end - start_date.hour)<max_duration:
            new_date = start_date +datetime.timedelta(days=1)
            start_date = datetime.datetime(new_date.year,new_date.month, new_date.day, model_test.get_shift_begin())
        return start_date


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
        end_date = datetime.datetime(date.year,date.month,date.day,end_shift)
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
            raise ValidationError('Duration should not qual 0')

    @api.depends('date', 'duration')
    def _compute_expiration_date(self):
        for rec in self:
           if rec.date:
               add_hours = datetime.timedelta(hours=rec.duration)
               rec.expiration_date = rec.date + add_hours

    def _set_start_expiration_dates(self):
        ircp = self.env['ir.config_parameter'].sudo()
        max_duration = int(ircp.get_param('tests_accounting.max_test_duration'))
        end_shift = self.get_shift_end()
        duration = self.duration if self.duration else max_duration
        add_hours = datetime.timedelta(hours=self.duration)
        start_time = datetime.datetime.now()-datetime.timedelta(hours=max_duration)
        start_time = self.tester_id.get_free_date(start_time, max_duration)
        bd = self.date if self.date else start_time 
        bd_h = bd.hour
        bd_m = bd.minute
        if (bd_h+duration)>end_shift:
            bd = bd + datetime.timedelta(hours=(24-bd_h+start_shift))
            bd_h = bd.hour
        elif bd_m!=0:
            bd_h += 1

        new_start = datetime.datetime(bd.year,bd.month,bd.day,bd_h)
        new_exp = new_start + add_hours
        self.date = new_start
        self.expiration_date = new_exp

    @api.onchange('tester_id')
    def on_change_tester_id(self):
        for rec in self:
            if rec.tester_id:
                rec._set_start_expiration_dates()



