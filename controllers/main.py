from odoo import http
from odoo.http import request
import datetime


class main(http.Controller):

    @http.route('/web/session/authenticate/', type="json", auth="none")
    def autorization(self,**kw):
        session_id = request.session.authenticate(request.session.db, kw['login'], kw['password'])
        return {'session_id':session_id}

    @http.route('/mytest/tests_by_status/', methods=["OPTIONS"], type="json", auth="user")
    def tests_by_status(self, **kw):
        if not kw.get('status'):
            return {'error','should pass status'}
        tests = request.env['tests.accounting.test'].sudo().search([('state','=',kw.get('status'))])
        return {'test_ids':tests.read(['id'])}

    @http.route('/mytest/available_testers', methods=["OPTIONS"], type="json", auth="user")
    def available_testers(self, **kw):
        if not kw.get('max_days') or not kw.get('test_duration'):
            return {'error':'should pass max_days and test_duration'}
        max_days = kw.get('max_days')
        test_duration = kw.get('test_duration')
        today = datetime.datetime.now()
        return {'testers_ids': request.env['tests.accounting.tester'].get_available_testers(today, max_days, test_duration)}
