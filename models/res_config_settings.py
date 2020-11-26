from odoo import models, api, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    max_test_duration = fields.Integer(string="Max Test Duration (hours)", implied_group="tests_accounting.group_tests_admin")
    work_shift_begin = fields.Integer(string="Work Shift Begin at ", implied_group="tests_accounting.group_tests_admin")
    work_time = fields.Integer(string="Testers Work time", implied_group="tests_accounting.group_tests_admin")

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        model_config_param = self.env['ir.config_parameter']
        model_config_param.set_param('tests_accounting.max_test_duration', self.max_test_duration)
        model_config_param.set_param('tests_accounting.work_shift_begin', self.work_shift_begin)
        model_config_param.set_param('tests_accounting.work_time', self.work_time)
        return res

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        model_config_param = self.env['ir.config_parameter']
        max_duration = model_config_param.get_param('tests_accounting.max_test_duration')
        work_begin = model_config_param.get_param('tests_accounting.work_shift_begin')
        work_time_param = model_config_param.get_param('tests_accounting.work_time')
        res.update(max_test_duration=int(max_duration), work_shift_begin=int(work_begin), work_time=int(work_time_param))
        return res
