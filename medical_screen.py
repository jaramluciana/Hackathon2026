"""Drop-in Flet screen for existing Hollow City app.
Call show(page, user_id, level, on_back) from screens/home.py.
"""
import flet as ft
import hollow_med_sql as med
from theme import BG_TOP, CARD_BG, ACCENT, TEXT, TEXT_DIM, ERROR, SUCCESS


def show(page, user_id, level, on_back):
    page.controls.clear()
    status=ft.Text('',color=SUCCESS)
    try:
        data=med.resident_dashboard(user_id)
        overview=data['level']
        health=data['resident']['health']
        summary=(f"Level {overview['level']}  |  Residents: {overview['population']:,}  |  "
                 f"Alive: {overview['alive']:,}  |  Health score: {health if health is not None else 'unavailable'}")
        conditions='   •   '.join(f'{k}: {v:.0f}%' for k,v in overview['systems'].items())
        clinic_list=med.clinics()
    except Exception as exc:
        page.add(ft.Column([ft.Button('BACK',on_click=lambda e:on_back()),
                            ft.Text('Healthcare unavailable: '+str(exc),color=ERROR)]))
        page.update(); return

    clinic_options=[ft.dropdown.Option(key=str(c['id']),text=f"L{c['level']} {c['name']} ({c['available']} slots)") for c in clinic_list]
    clinic_dropdown=ft.Dropdown(label='Clinic',options=clinic_options,width=400)
    kind_dropdown=ft.Dropdown(label='Request type',value='medical',width=250,options=[
        ft.dropdown.Option('medical'),ft.dropdown.Option('emergency'),ft.dropdown.Option('supplies')])
    message=ft.TextField(label='Describe what you need',multiline=True,min_lines=2,max_lines=4,width=500)

    def request(e):
        try:
            status.value=med.submit_request(user_id,kind_dropdown.value,message.value or '')
            status.color=SUCCESS
        except Exception as exc:
            status.value=str(exc);status.color=ERROR
        page.update()

    def book(e):
        try:
            if not clinic_dropdown.value: raise ValueError('Select a clinic first')
            status.value=med.book_appointment(user_id,int(clinic_dropdown.value))
            status.color=SUCCESS
        except Exception as exc:
            status.value=str(exc);status.color=ERROR
        page.update()

    def section(title,controls):
        return ft.Container(bgcolor=CARD_BG,padding=18,border_radius=8,
                            content=ft.Column([ft.Text(title,size=18,color=ACCENT),*controls],spacing=10))

    notice_controls=[ft.Text(n['message'],color=TEXT,size=13) for n in data['notifications'][:8]]
    if not notice_controls: notice_controls=[ft.Text('No current announcements',color=TEXT_DIM)]
    request_controls=[ft.Text(f"#{r['id']} {r['kind']} — {r['status']}: {r['message']}",color=TEXT,size=13)
                      for r in data['requests'][:8]]
    if not request_controls: request_controls=[ft.Text('No requests yet',color=TEXT_DIM)]
    appt_controls=[ft.Text(f"Appointment #{a['id']} — Clinic {a['clinic_id']}: {a['status']}",color=TEXT,size=13)
                   for a in data['appointments'][:8]]
    if not appt_controls: appt_controls=[ft.Text('No appointments yet',color=TEXT_DIM)]
    page.add(ft.Container(expand=True,bgcolor=BG_TOP,padding=25,content=ft.Column([
        ft.Row([ft.Button('← BACK',on_click=lambda e:on_back()),
                ft.Text('HOLLOW-MED',size=28,color=ACCENT)],spacing=20),
        section('YOUR HEALTH & LEVEL',[ft.Text(summary,color=TEXT),ft.Text(conditions,color=TEXT_DIM)]),
        section('REQUEST AN APPOINTMENT',[clinic_dropdown,ft.Button('REQUEST APPOINTMENT',on_click=book),*appt_controls]),
        section('MEDICAL ASSISTANCE',[kind_dropdown,message,ft.Button('SUBMIT REQUEST',on_click=request),*request_controls]),
        section('ANNOUNCEMENTS',notice_controls),status,
    ],scroll=ft.ScrollMode.AUTO,spacing=14)))
    page.update()
