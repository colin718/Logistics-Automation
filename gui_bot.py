import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
import tkinter as tk
import pandas as pd
import os
import datetime
import json
import threading
import sys
from urllib.request import urlopen
from dateutil import parser 

SHEET_URL = "YOUR_GOOGLE_SHEET_URL"

# 체험판 기간 설정 (일)
TRIAL_DAYS = 7
SECRET_FILE_NAME = "logistics_license_key.dat"     # 인증키 저장 파일명
TRIAL_FILE_NAME = "logistics_trial_date.dat"       # 체험판 기록 파일명
CONFIG_FILE = "config.json"                        # 택배사 설정 파일명

# 1. 라이선스 & 구독 관리 시스템
def get_network_time():
    """사용자 PC 시간이 아닌, 구글 서버의 정확한 시간을 가져옵니다."""
    try:
        res = urlopen('http://www.google.com', timeout=3)
        date_str = res.headers['Date']
        return parser.parse(date_str).replace(tzinfo=None)
    except Exception:
        return datetime.datetime.now()

def check_subscription():
    """
    1. 체험판 기간인지 확인
    2. 체험판 끝났으면 -> 저장된 인증키 확인
    3. 인증키로 구글 시트 조회 -> 유효기간 남았는지 확인
    """
    appdata_path = os.getenv('APPDATA')
    license_file = os.path.join(appdata_path, SECRET_FILE_NAME)
    trial_file = os.path.join(appdata_path, TRIAL_FILE_NAME)
    
    current_time = get_network_time()
    
    # 체험판 체크 (인증키 파일이 없을 때만)
    if not os.path.exists(license_file):
        if not os.path.exists(trial_file):
            # 오늘 처음 켠 사람이면 체험판 시작 날짜 기록
            expiry_date = current_time + datetime.timedelta(days=TRIAL_DAYS)
            try:
                with open(trial_file, "w") as f:
                    f.write(expiry_date.strftime("%Y-%m-%d"))
                messagebox.showinfo("체험판 안내", f"반갑습니다!\n오늘부터 {TRIAL_DAYS}일 동안 무료로 체험하실 수 있습니다.")
                return 
            except Exception:
                pass # 파일 생성 실패해도 일단 넘어가거나 종료 처리
        else:
            # 체험판 기록이 있는 사람은 날짜 지났는지 확인
            try:
                with open(trial_file, "r") as f:
                    trial_end_str = f.read().strip()
                trial_end_date = datetime.datetime.strptime(trial_end_str, "%Y-%m-%d")
                
                if current_time <= trial_end_date + datetime.timedelta(days=1):
                    return
            except Exception:
                pass

    # 체험판 만료되면 정식 인증 절차
    user_key = ""
    
    # 이미 저장된 인증키가 있으면 불러오기
    if os.path.exists(license_file):
        with open(license_file, "r") as f:
            user_key = f.read().strip()
    
    # 키 검증 루프
    while True:
        # 키가 없으면 입력받기
        if not user_key:
            root = tk.Tk()
            root.withdraw()
            user_key = simpledialog.askstring("기간 만료", "체험 기간이 끝났습니다.\n발급받은 인증키(예: 휴대폰번호)를 입력하세요.")
            root.destroy()
            
            if not user_key:
                sys.exit()
        
        # 구글 시트 조회 (서버 체크)
        try:
            # pandas로 구글 시트 CSV 읽기
            try:
                df = pd.read_csv(SHEET_URL, dtype=str)
            except Exception:
                 # 시트 URL이 잘못되었거나 인터넷 문제일 경우
                messagebox.showerror("접속 오류", "서버에 연결할 수 없습니다. 인터넷 상태를 확인하거나 관리자에게 문의하세요.")
                sys.exit()

            # 내 키가 엑셀에 있는지 찾기
            # 구글시트 헤더가 무조건 LicenseKey, ExpirationDate
            if 'LicenseKey' not in df.columns or 'ExpirationDate' not in df.columns:
                 messagebox.showerror("시스템 오류", "서버 설정(컬럼명)이 잘못되었습니다. 관리자에게 문의하세요.")
                 sys.exit()

            user_row = df[df['LicenseKey'] == user_key]
            
            if user_row.empty:
                messagebox.showerror("인증 실패", "등록되지 않은 인증키입니다.\n관리자에게 문의해주세요.")
                user_key = "" 
                if os.path.exists(license_file): os.remove(license_file)
                continue
            
            # 날짜 확인
            exp_date_str = user_row.iloc[0]['ExpirationDate'] 
            try:
                exp_date = datetime.datetime.strptime(exp_date_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("오류", "유효기간 형식이 잘못되었습니다.")
                sys.exit()
            
            if current_time > exp_date + datetime.timedelta(days=1):
                messagebox.showerror("기간 만료", f"구독 기간이 종료되었습니다.\n(만료일: {exp_date_str})\n\n연장을 원하시면 연락주세요.")
                sys.exit()
            else:
                # 키를 파일에 저장해둠
                with open(license_file, "w") as f:
                    f.write(user_key)
                break 
                
        except Exception as e:
            messagebox.showerror("오류", f"인증 중 알 수 없는 오류가 발생했습니다.\n{str(e)}")
            sys.exit()

# 2. 설정 파일 로직
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {} 

def save_config(courier_name):
    data = {"courier_name": courier_name}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 3. 도우미 함수
def find_column_name(df, keywords):
    for col in df.columns:
        col_str = str(col).replace(" ", "")
        for key in keywords:
            if key in col_str:
                return col
    return None

def get_last_4_digits(phone_number):
    clean_num = ''.join(filter(str.isdigit, str(phone_number)))
    if len(clean_num) >= 4:
        return clean_num[-4:]
    else:
        return clean_num

# 4. 핵심 분석 로직 (매칭 + 누락자 리포트)
def run_analysis():
    try:
        order_path = entry_order.get()
        tracking_path = entry_tracking.get()
        my_courier_name = combo_courier.get()
        
        order_df = pd.read_excel(order_path, dtype=str)       
        courier_df = pd.read_excel(tracking_path, dtype=str)   
        
        name_col_naver = find_column_name(order_df, ['수취인명', '구매자명', '받는사람', '수령인'])
        phone_col_naver = find_column_name(order_df, ['수취인연락처', '연락처', '전화번호', 'Phone', 'Mobile'])
        track_col_naver = find_column_name(order_df, ['송장번호', '운송장', 'Tracking'])
        company_col_naver = find_column_name(order_df, ['택배사', '배송업체'])

        # 주소 컬럼 찾기 (기본+상세)
        addr_basic_col = find_column_name(order_df, ['기본배송지', '주소', 'Address', '배송지'])
        addr_detail_col = find_column_name(order_df, ['상세배송지', '상세주소', 'Detail'])

        if not track_col_naver:
            track_col_naver = '송장번호'
            order_df[track_col_naver] = ""
        if not company_col_naver:
            company_col_naver = '택배사'
            order_df[company_col_naver] = ""

        name_col_courier = find_column_name(courier_df, ['수취인', '구매자', '받는사람', '받는분', '고객'])
        phone_col_courier = find_column_name(courier_df, ['수취인연락처', '연락처', '전화번호', 'Phone', 'Mobile'])
        track_col_courier = find_column_name(courier_df, ['송장', '운송장', 'Tracking', 'Invoice'])

        if not name_col_naver or not phone_col_naver:
             stop_loading()
             messagebox.showerror("오류", "네이버 파일에서 [이름] 또는 [연락처]를 찾을 수 없습니다.")
             return
        if not name_col_courier or not phone_col_courier or not track_col_courier:
            stop_loading()
            messagebox.showerror("오류", "택배사 파일에서 필수 정보(이름/연락처/송장)를 찾을 수 없습니다.")
            return

        # 매칭 작업
        order_names = order_df[name_col_naver].str.strip()
        order_phones = order_df[phone_col_naver].apply(get_last_4_digits)
        order_df['MATCH_KEY'] = order_names + "_" + order_phones

        courier_names = courier_df[name_col_courier].str.strip()
        courier_phones = courier_df[phone_col_courier].apply(get_last_4_digits)
        courier_df['MATCH_KEY'] = courier_names + "_" + courier_phones

        def clean_tracking_no(no):
            no = str(no).strip()
            if no.endswith('.0'): no = no[:-2]
            if no.lower() == 'nan': return ''
            return no
        courier_df[track_col_courier] = courier_df[track_col_courier].apply(clean_tracking_no)

        tracking_map = dict(zip(courier_df['MATCH_KEY'], courier_df[track_col_courier]))
        mapped_values = order_df['MATCH_KEY'].map(tracking_map)
        
        # 송장번호 업데이트
        order_df[track_col_naver] = mapped_values.fillna(order_df[track_col_naver])
        
        # 택배사 업데이트 (매칭된 것만)
        mask_success = (mapped_values.notnull()) & (mapped_values != '')
        order_df.loc[mask_success, company_col_naver] = my_courier_name

        del order_df['MATCH_KEY']
        
        # 결과 분류
        success_df = order_df[mask_success] # 성공
        fail_df = order_df[~mask_success]   # 실패 (누락자)

        today = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. 성공 파일 저장
        save_path_ok = None
        if not success_df.empty:
            save_path_ok = os.path.join(os.getcwd(), f"[업로드용]송장완료_{today}.xlsx")
            success_df.to_excel(save_path_ok, index=False)

        # 2. 실패 파일 저장 (누락자 리포트)
        save_path_fail = None
        if not fail_df.empty:
            save_path_fail = os.path.join(os.getcwd(), f"[확인필요]미발송명단_{today}.xlsx")
            fail_df.to_excel(save_path_fail, index=False)

        count_ok = len(success_df)
        count_fail = len(fail_df)
        
        stop_loading()
        
        # 3. 결과 메시지
        if count_ok == 0:
            messagebox.showwarning("결과", "매칭된 송장이 하나도 없습니다!\n이름과 전화번호를 확인해주세요.")
        elif count_fail == 0:
            messagebox.showinfo("완벽 성공! 🎉", f"총 {count_ok}건 모두 매칭되었습니다!\n\n누락된 건이 없습니다.\n[업로드용] 파일이 열립니다.")
            if save_path_ok: os.startfile(save_path_ok)
        else:
            msg = f"✅ 매칭 성공: {count_ok}건\n❌ 매칭 실패: {count_fail}건\n\n[확인필요] 미발송 명단 파일이 생성되었습니다.\n꼭 확인해주세요!"
            messagebox.showinfo("작업 완료", msg)
            if save_path_ok: os.startfile(save_path_ok)
            if save_path_fail: os.startfile(save_path_fail)

    except Exception as e:
        stop_loading()
        messagebox.showerror("에러", f"오류 발생:\n{str(e)}")

def start_process():
    order_path = entry_order.get()
    tracking_path = entry_tracking.get()
    my_courier_name = combo_courier.get()
    
    if not order_path or not tracking_path:
        messagebox.showerror("알림", "파일 2개를 모두 선택해주세요.")
        return
    if not my_courier_name or my_courier_name == "택배사를 선택하거나 직접 입력하세요":
        messagebox.showerror("알림", "택배사를 선택하거나 입력해주세요.")
        return

    save_config(my_courier_name)
    
    btn_start.configure(text="데이터 정밀 분석 중...", state="disabled", fg_color="#333333")
    progress_bar.pack(pady=(0, 20), padx=30, fill="x")
    progress_bar.start()
    
    threading.Thread(target=run_analysis, daemon=True).start()

def stop_loading():
    progress_bar.stop()
    progress_bar.pack_forget()
    btn_start.configure(text="지금 매칭 시작하기", state="normal", fg_color="#2563EB")

def select_file(entry_widget):
    filename = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
    if filename:
        entry_widget.delete(0, 'end')
        entry_widget.insert(0, filename)

# 5. GUI 디자인 (Modern)
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue") 

app = ctk.CTk()

check_subscription()

app.title("Logistics Sync Pro")
app.geometry("540x680")
app.configure(fg_color="#F5F6FA")

FONT_BOLD = ("AppleSDGothicNeo-Bold", 16) 
FONT_NORMAL = ("AppleSDGothicNeo-Regular", 14)
FONT_TITLE = ("AppleSDGothicNeo-Bold", 28)

lbl_title = ctk.CTkLabel(app, text="송장 자동 매칭 프로그램", font=("AppleSDGothicNeo-Regular", 32, "bold"), text_color="#1A1A1A")
lbl_title.pack(pady=(50, 5))

lbl_sub = ctk.CTkLabel(app, text="주문서와 배송장을 자동 매칭하고, 누락된 건까지 완벽하게 검증합니다.", font=FONT_NORMAL, text_color="#718096")
lbl_sub.pack(pady=(0, 30))

main_card = ctk.CTkFrame(app, fg_color="#FFFFFF", corner_radius=25, width=480)
main_card.pack(pady=0, padx=30, fill="both", expand=True)

inner_frame = ctk.CTkFrame(main_card, fg_color="transparent")
inner_frame.pack(pady=30, padx=30, fill="both", expand=True)

# 1. 네이버 주문서
lbl_order = ctk.CTkLabel(inner_frame, text="네이버 주문서", font=("AppleSDGothicNeo-Regular", 16, "bold"), text_color="#2D3748")
lbl_order.pack(anchor="w", pady=(0, 10))
frame_input1 = ctk.CTkFrame(inner_frame, fg_color="transparent")
frame_input1.pack(fill="x", pady=(0, 20))

entry_order = ctk.CTkEntry(frame_input1, placeholder_text="파일 선택...", font=FONT_NORMAL, 
                           height=50, corner_radius=20, 
                           fg_color="#EDF2F7", border_width=0, text_color="black")
entry_order.pack(side="left", fill="x", expand=True, padx=(0, 10))

btn_order = ctk.CTkButton(frame_input1, text="찾기", font=("AppleSDGothicNeo-Bold", 13), 
                          width=70, height=50, corner_radius=20, 
                          fg_color="#2563EB", hover_color="#1D4ED8", text_color="#FFFFFF", 
                          command=lambda: select_file(entry_order))
btn_order.pack(side="right")

# 2. 택배사 리스트
lbl_tracking = ctk.CTkLabel(inner_frame, text="택배사 리스트", font=("AppleSDGothicNeo-Regular", 16, "bold"), text_color="#2D3748")
lbl_tracking.pack(anchor="w", pady=(0, 10))

frame_input2 = ctk.CTkFrame(inner_frame, fg_color="transparent")
frame_input2.pack(fill="x", pady=(0, 20))

entry_tracking = ctk.CTkEntry(frame_input2, placeholder_text="파일 선택...", font=FONT_NORMAL, 
                              height=50, corner_radius=20, 
                              fg_color="#EDF2F7", border_width=0, text_color="black")
entry_tracking.pack(side="left", fill="x", expand=True, padx=(0, 10))

btn_tracking = ctk.CTkButton(frame_input2, text="찾기", font=("AppleSDGothicNeo-Bold", 13), 
                             width=70, height=50, corner_radius=20,
                             fg_color="#2563EB", hover_color="#1D4ED8", text_color="#FFFFFF",
                             command=lambda: select_file(entry_tracking))
btn_tracking.pack(side="right")

# 3. 택배사 이름 설정
lbl_courier = ctk.CTkLabel(inner_frame, text="택배사 선택", font=("AppleSDGothicNeo-Regular", 16, "bold"), text_color="#2D3748")
lbl_courier.pack(anchor="w", pady=(0, 10))

courier_list = [
    "CJ대한통운", "우체국택배", "한진택배", "롯데택배", "로젠택배","GS25편의점택배",
    "CU 편의점택배", "경동택배", "대신택배", "일양로지스", "합동택배", "건영택배"
]

combo_courier = ctk.CTkComboBox(inner_frame, 
                                values=courier_list,
                                font=FONT_NORMAL,
                                height=50, corner_radius=20,
                                fg_color="#EDF2F7", border_width=0, text_color="black",
                                dropdown_fg_color="white",
                                dropdown_text_color="black",
                                dropdown_font=FONT_NORMAL)
combo_courier.pack(fill="x")

saved_config = load_config()
if saved_config and "courier_name" in saved_config:
    combo_courier.set(saved_config["courier_name"]) 
else:
    # 설정이 없으면 기본 안내 문구 표시
    combo_courier.set("택배사를 선택하거나 직접 입력하세요")

# 실행 버튼 & 프로그레스 바
btn_start = ctk.CTkButton(app, text="지금 매칭 시작하기", font=("AppleSDGothicNeo-Bold", 18), 
                          height=60, corner_radius=30, 
                          fg_color="#2563EB", hover_color="#1D4ED8", 
                          command=start_process)
btn_start.pack(pady=(30, 20), padx=30, fill="x")

progress_bar = ctk.CTkProgressBar(app, height=15, corner_radius=10, 
                                  progress_color="#2563EB", fg_color="#E2E8F0")
progress_bar.set(0)

app.mainloop()