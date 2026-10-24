using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Text;
using System.Collections;
using System.Windows.Forms;
using System.Threading;
using System.IO;
using System.Diagnostics;
using LVClient.HTMLParse;
using LVClient.Command.CityObj;
using LVClient.Command.CommonObj;

namespace LVClient 
{
    public partial class frmmain : Form 
	{

        private const string version = "5.2";
		public string strVersion = "";

		
		private Boolean IsLogin = false;
        private int CountTick = 0;
        private int upgradepost = 0;
		public  static LVThread.BUILD LVBUILD ;
		public static LVThread.DEL LVDEL;
		public static LVThread.SELL LVSELL;
		public static LVThread.BUYRES LVBUYRES;
		public static LVThread.THAOPHAT LVTHAOPHAT;
		public static LVThread.UPGRADE LVUPGRADE;
		public static LVThread.ANUI LVANUI;
		public static LVThread.VANCHUYEN LVVANCHUYEN;
		public static LVThread.MOVEDOANHTRAI LVMOVEDOANHTRAI;
		public static LVThread.SIKHI LVSIKHI;
		public static LVThread.BUYWEPON LVBUYWEPON;
		public static LVThread.CITYTASK LVCITYTASK;
		public static LVThread.BIENCHE LVBIENCHE;
		public static LVThread.PHAIQUANVANDAOMO LVDAOMO;
		public static LVThread.LOIDAI LVLOIDAI;
		public static LVThread.AUTOTASK LVAUTOTASK;
		public static LVThread.AUTOVANCHUYENVK LVAUTOVCVK;
		public static LVThread.AUTOBINHMAN LVAUTOBINHMAN;
		public static LVThread.AUTOCALLMAN LVAUTOCALLMAN;


		public static LVClient.frmmain LVFRMMAIN;

		public static Label _lblLoading;

		public static ArrayList ListBienChe = new ArrayList(); // List danh sach bien che
		//public static LVClient.Common.PhaiQuanVanDaoMo QuanVanDaoMo = new LVClient.Common.PhaiQuanVanDaoMo();
		//public static LVClient.Common.GeneralThaoPhat TuongDiThaoPhat = new LVClient.Common.GeneralThaoPhat();
		public static ArrayList TuongDiThaoPhatList = new ArrayList();//  LVClient.Common.GeneralThaoPhat;

		public static ArrayList AnuiForAuto = new ArrayList();
		public static ArrayList UpgradeForAuto = new ArrayList();			// nang cap trong dai hoc dien [0]: cityid; [1->]: id can nang cap
		
		public static ArrayList DieuPhaiQuanVanVo = new ArrayList();
		public static Command.CommonObj.BanTaiNguyenObj BanTaiNguyen = new LVClient.Command.CommonObj.BanTaiNguyenObj();
		public static Command.CommonObj.MuaTaiNguyenObj MuaTaiNguyen = new LVClient.Command.CommonObj.MuaTaiNguyenObj();
		public static ArrayList DiChuyenTrai = new ArrayList();
		public static ArrayList VanChuyenVuKhi = new ArrayList();
		public static ArrayList BinhManList = new ArrayList();
		public static ArrayList CallManList = new ArrayList(); //LVClient.Command.CommonObj.CallManObj


		public static bool TuLinhBongLoc = true;
		public static bool ThongBaoDanhTuongViengTham = true;
		//public static string DanhTuongDangViengTham = "";
		public static bool TuBanThuongDoDe = true;
		public static bool TuBanAnUiKhiDanNo = true;
		public static bool TuXoaNhacNhoCuaAdmin = true;

		public static  int _tuxacnhananh = 1;  //0: ko lam gi ca; 1: hien anh; 2: tu xac nhan
		public static bool _chuongbao = false;
		public static int imagecheckid;

		public bool SellResource_loaded = false;
		public bool BuyResource_loaded = false;
		public bool Anui_loaded				= false;
		public bool BuildCity_loaded = false;
		public bool DelCity_loaded = false;
		public bool ThaoPhat_loaded = false;
		public bool ReSearch_loaded = false;

		public bool VanChuyen_loaded = false;
		public bool MoveDoanhTrai_loaded = false;
		public bool Upsikhi_loaded = false;
		public bool BuyWepon_loaded = false;

		private string fileSavepath = "";

		private bool bantaiNguyenLuaCheckAll = true;
		private bool bantaiNguyenGoCheckAll = true;
		private bool bantaiNguyenSatCheckAll = true;
		private bool bantaiNguyenDaCheckAll = true;

		private bool muataiNguyenLuaCheckAll = true;
		private bool muataiNguyenGoCheckAll = true;
		private bool muataiNguyenSatCheckAll = true;
		private bool muataiNguyenDaCheckAll = true;

		private Hashtable QuocKho_Ruong = new Hashtable();
		
		
		// ban tai nguyen
		private int BanTNSoLuongBanCoDinhDefault = 1000;
		private int BanTNSoLuongBanPercentDefault = 30;
		private int BanTNAnToanCoDinhDefault = 500;
		private int BanTNAnToanPercentDefault = 60;

		public int SoLanTuCheckAnhSaiLienTiep = 0;
		public DateTime LastTimeImageCheck = DateTime.Now;


		// for proxy

		public static string ProxyProtocol;
		public static string ProxyServer;
		public static string ProxyPort;
		public static string ProxyUser;
		public static string ProxyPass;
 
		public frmmain() 
		{
            InitializeComponent();

			timerForTBDanhTuongViengTham.Start();
        }

		private  void frmmain_Load(object sender, EventArgs e) 
		{
			try
			{

            //FirstLogin();
			LVFRMMAIN = this;

			string str = Directory.GetCurrentDirectory();


			// Disable all tabpage
			for (int i = 1; i < tabMainTab.TabPages.Count; i++)
			{
				tabMainTab.TabPages[i].Enabled = false;
			}

			
			txtUsername.Focus();
		
			panelLoading.BringToFront();
			panelLoading.Visible = false;
			//lblmainmsg.Text = "";
			picAttach.Visible = false;

            try
            {
                //load server
                System.Xml.XmlDocument xmld;
                System.Xml.XmlNodeList nodelist;

                //Create the XML Document
                xmld = new System.Xml.XmlDocument();
                //Load the Xml file
                xmld.Load("ServerList.xml");
                //Get the list of name nodes 
                string notepath = "AutoLinhVuong";
                //node = xmld.SelectSingleNode(notepath);

                //Get the list of name nodes 
                notepath = "/AutoLinhVuong/tan";
                nodelist = xmld.SelectNodes(notepath);

                System.Collections.ArrayList re = new System.Collections.ArrayList();
                for (int ii = 0; ii < nodelist.Count; ii++)
                {
                    re.Add(nodelist[ii].InnerText);
                }
                if (re.Count > 0)
                {
                    cboServer.Items.Clear();
                    cboServer.Items.AddRange(re.ToArray());
                }
            }
            catch (Exception ex)
            {

            }
				//remove for release
				
				
#if (DEBUG)

                strVersion =  "LVClient Debug " + version;

                chkTabBinhManListManDanh.Items.Clear();
                chkTabBinhManListManDanh.Items.Add("1. Uy Quốc");
                chkTabBinhManListManDanh.Items.Add("2. Tiên Ti");
                chkTabBinhManListManDanh.Items.Add("3. Ô hoàn");
                chkTabBinhManListManDanh.Items.Add("4. Sơn việt");
                chkTabBinhManListManDanh.Items.Add("5. Khương để");
                chkTabBinhManListManDanh.Items.Add("6. Mạnh hoạch");
                chkTabBinhManListManDanh.Items.Add("7. Hung nô");
                chkTabBinhManListManDanh.Items.Add("101. Quân lương");
                chkTabBinhManListManDanh.Items.Add("201. Thần thú");

                txtTabBinhManMaxODi.Text = "50";

#else
                //tabMainTab.Controls.Remove(tabBinhMan);
                //chkAUTOBINHMAN.Visible = false;
				//lblAUTOBINHMANMESSAGE.Visible = false;

                strVersion =  "LVClient Release " + version;

                chkTabBinhManListManDanh.Items.Add("101. Quân lương");
                chkTabBinhManListManDanh.Items.Add("201. Thần thú");
                txtTabBinhManMaxODi.Text = "10";
#endif


                this.Text = strVersion;
                txtUsername.Focus();
				
			}
			catch (Exception ex)
			{

			}
        }
		public void SetAllMainTabEnable(bool enable)
		{
			for (int i = 0; i < tabMainTab.TabPages.Count; i++)
			{
				tabMainTab.TabPages[i].Enabled = enable;
			}
		}

		public bool FirstLogin_()
		{
			notifyIcon1.Text = "Đang load dữ liệu, vui lòng chờ. Máy có thể đứng đó.";
			
			
			if (LVClient.Web.LVWeb.LoginHtml != null)
			{
				while (true)
				{
					try
					{
						// enable tabage
						for (int i = 1; i < tabMainTab.TabPages.Count; i++)
						{
							tabMainTab.TabPages[i].Enabled = true;
						}

						Hashtable lastlogindata = Web.ParseHeader.GetDataFromForm(LVClient.Web.LVWeb.LoginHtml);
						Hashtable lastlogin = Web.LVWeb.LoginPartner(lastlogindata["uid"].ToString(), lastlogindata["uname"].ToString(), lastlogindata["ulgtime"].ToString(), lastlogindata["pid"].ToString(), lastlogindata["sign"].ToString());
						Web.LVWeb.CurrentLoginInfo = new Web.LoginInfo((string[])lastlogin["Set-Cookie"]);

						//Command.City.GetAllSimpleCity();
						
						//Command.City.UpdateAllSimpleCity();
						//Command.City.GetAllCity();


						chkAutoAll.Enabled = true;
						IsLogin = true;
						notifyIcon1.Text = strVersion;//"LVClient";

						// bao bi tan cong, hungtv rem
						LVCITYTASK = new LVClient.LVThread.CITYTASK();
						LVCITYTASK.Auto();

						LVAUTOTASK = new LVClient.LVThread.AUTOTASK(lblLoadingResMessage);
						LVAUTOTASK.Auto();

						LVBUILD = new LVClient.LVThread.BUILD(lblBUILDMESSAGE);
						
						LVDEL = new LVClient.LVThread.DEL(lblDELMESSAGE);
						LVSELL = new LVClient.LVThread.SELL(lblSELLMESSAGE);
						LVBUYRES = new LVClient.LVThread.BUYRES(lblBUYRESMESSAGE);
						LVTHAOPHAT = new LVClient.LVThread.THAOPHAT(lblTHAOPHATMESSAGE);
						LVUPGRADE = new LVClient.LVThread.UPGRADE(lblUPGEADEMESSAGE);
						LVANUI = new LVClient.LVThread.ANUI(lblANUIMESSAGE);
						LVVANCHUYEN = new LVClient.LVThread.VANCHUYEN(lblVANCHUYENMESSAGE);
						LVMOVEDOANHTRAI = new LVClient.LVThread.MOVEDOANHTRAI(lblMOVEDOANHTRAI);
						LVSIKHI = new LVClient.LVThread.SIKHI(lblSIKHIMESSAGE);
						LVBUYWEPON = new LVClient.LVThread.BUYWEPON(lblBUYWEPONMESSAGE);
						
						LVBIENCHE = new LVClient.LVThread.BIENCHE(lblBIENCHEMESSAGE);
						LVDAOMO = new LVClient.LVThread.PHAIQUANVANDAOMO(lblDIEUPHAIMESSAGE);
						LVLOIDAI = new LVClient.LVThread.LOIDAI(lblDIEUPHAIMESSAGE);

						LVAUTOVCVK = new LVClient.LVThread.AUTOVANCHUYENVK(lblAUTOVCVKMESSAGE);
						//LVCITYTASK.IsRun = true;
						LVAUTOBINHMAN = new LVClient.LVThread.AUTOBINHMAN(lblAUTOBINHMANMESSAGE);
						LVAUTOCALLMAN = new LVClient.LVThread.AUTOCALLMAN(lblAUTOCALLMANMESSAGE);

						

						LVClient.Web.LVWeb.debug = false;
						LVClient.Web.LVWeb.firstlogin = false;

						tabLogin.Select();
						tabLogin.Focus();

						Thread.Sleep(5000);
						break;
					}
					catch (Exception ex)
					{
						//MessageBox.Show(ex.ToString());
						return false;
					}
				} // end 	while (true)
				return true;
			}
			else
			{
				Application.Exit();
			}
			return false;
		}

		private void tabControl1_Selected(object sender, TabControlEventArgs e)
		{

			//int x = Command.Common.MapIDtoX(1159002);
			//int y = Command.Common.MapIDtoY(1159002);

				try
				{
			/*
						0: Login
						1: Auto
						2: Bantainguyen
						3: MuataiNguyen
						4: XayDung:
						5: Hanha
						6: thaophat
						7: NghienCuu
						8: anui
						9: Vanchuyen
						10:Doitrai
						11: luýenyKhi
						12: Muavukhi
						13: tienich
						14: SMS
						//MessageBox.Show(tabControl1.TabPages[tabControl1.SelectedIndex].Text);
				
	
			 */

					

				
			//switch (tabMainTab.SelectedIndex) 
			switch (tabMainTab.SelectedTab.Name.ToLower().Trim())
			{
					

				case "tablogin":						//"Login":
					break;
				case "tbauto":						//"Auto":
					break;
				case "tabbantainguyen":						//"Ban tai nguyen":
					if (!SellResource_loaded)
					{
						Common.common.LoadCityToGridForSellResource(this.dtaSELL);
			/*
						while (true)
						{
							try
							{
								LoadAvgPrice();
								break;
							}
							catch (Exception ex)
							{
							}
						}

			 */ 
						SellResource_loaded = true;
					}
					break;

				case "tabmuatainguyen":						//Mua taif nguyen
					if (!BuyResource_loaded)
					{
						Common.common.LoadCityToGridForBuyResource(this.dtaBUYRESOURCE);
						BuyResource_loaded = true;
					}
					break;

				case "tabxaydung":						// Xay dung
					//if (!BuildCity_loaded)
						{
							showLoadingLabel();
							//Application.DoEvents();

							cboXayDungCity.Items.Clear();
							cboXayDungCity.Items.AddRange(Command.CityObj.City.AllCity);
							//cboXayDungCity.SelectedIndex = 0;
							this.tvBUILD.Nodes.Clear();
							//Common.common.LoadBuildingToTreeViewForbuild_(this.tvBUILD, cboXayDungCity.SelectedIndex);
						// Common.common.LoadBuildingToTreeViewForbuild_(this.tvBUILD);
							BuildCity_loaded = true;
							hideLoadingLabel();
							//chkXayNhaAll.Checked = Command.CityObj.City.isBuildAll;
							//chkXayNha_TuMuaTaiNguyen.Checked = Command.CityObj.City.isBuyRes;
							//txtXayNha_VangAnToan.Text = Command.CityObj.City.goldSafe.ToString();
							

						}
						
					break;
				case "tabhanha":						// Ha nha						
					//if (!DelCity_loaded)
					{
						showLoadingLabel();
						cboTabHaNhaCity.Items.Clear();
						cboTabHaNhaCity.Items.AddRange(Command.CityObj.City.AllCity);
						this.tvDEL.Nodes.Clear();

						//Common.common.LoadBuildingToTreeViewForbuild(this.tvDEL);
						DelCity_loaded = true;
						hideLoadingLabel();
					}
					break;

				case "tabthaophat":						// Thao phat

					if (!ThaoPhat_loaded)
					{
						showLoadingLabel();
						LVClient.Common.common.LoadDataForThaoPhat(LVClient.frmmain.TuongDiThaoPhatList);
						
						
						/*
						while (true)
						{
							try
							{
								// lays danh sach cac nhiem vu
								Command.Common.GetMaxNhiemVu();
								break;
							}
							catch (Exception ex)
							{
							}
						}

						//cboThaoPhatSLTuongDanh1Dich.SelectedIndex = 0;
						//cboThaoPhatPhuongThucTanCong.SelectedIndex = 0;

						cboCity.Items.Clear();
						cboCity.Items.AddRange(Command.CityObj.City.AllCity);
						cboNhiemVu.Items.Clear();
						cboNhiemVu.Items.AddRange(Command.CommonObj.ThaoPhat.AllNhiemVu);

						
						Common.GeneralThaoPhat gen;
						if (TuongDiThaoPhatList.Count > 0)
						{
							gen = (Common.GeneralThaoPhat)TuongDiThaoPhatList[0];
							for (int i = 0; i < cboCity.Items.Count; i++)
								if (((Command.CityObj.City)cboCity.Items[i]).id == gen.CityID)
								{
									cboCity.SelectedIndex = i;
									break;
								}

							for (int i = 0; i < cboNhiemVu.Items.Count; i++)
								if (((Command.CommonObj.ThaoPhat)cboNhiemVu.Items[i]).id == gen.nhiemvuid)
								{
									cboNhiemVu.SelectedIndex = i;
									break;
								}


							txtTPCHECK.Text = gen.timetorun.ToString();
							txtThaoPhatSyKhi.Text = gen.SiKhiMinToGo.ToString();
							chkSKST.Checked = gen.TuUpSiKhi;
							chkThaoPhatBienCheThemQuan.Checked = gen.TuBienCheQuan;
							txtThaoPhatTongQuanMin.Text = gen.SoLuongQuanMinToGo.ToString();

						}
						*/

						ThaoPhat_loaded = true;
						hideLoadingLabel();
					}

					break;
				case "tabnghiencuu":						// Nghien cuu	
					if (!ReSearch_loaded)
					{
						cboCityForUpgrade.Items.Clear();
						cboCityForUpgrade.Items.AddRange(Command.CityObj.City.AllCity);
						Common.common.LoadUpgradeToTreeViewForUpdate(tvUpdate);

						ReSearch_loaded = true;
					}
					break;

				case "tabanui":						// An ui
					//if (!Anui_loaded)
					{
						//Common.common.LoadCityToGridForAnUi(dtaAnUi);
						Common.common.LoadCityToGridForAnUi(chklstAnUi);
						Anui_loaded = true;
					}
					break;
				case "tabvanchuyen":						//Van chuyen
					if (!VanChuyen_loaded)
					{
						Common.common.LoadCityToGridForVanchuyen(pnVanchuyen);
						VanChuyen_loaded = true;
					}
					break;
				case "tabdoitrai":		// Doi trai
					if (!MoveDoanhTrai_loaded)
					{
						Common.common.LoadDoanhTraiForMove(pnDoanhTrai);
						MoveDoanhTrai_loaded  = true;
					}
					break;
				case "tabluyensikhi":		// luyen sy khi
					if (!Upsikhi_loaded)
					{
						//cboLuyenSKCity.Items.Clear();
						//cboLuyenSKCity.Items.AddRange(Command.CityObj.City.AllCity);

						if (Common.common.LoadGeneralForUpSiKhi(tvSIKHI)) Upsikhi_loaded = true;
					}

					break;

				case "tabmuavukhi":		// mua vu khi
					if (!BuyWepon_loaded)
					{
						showLoadingLabel();
						if (Common.common.LoadCityForBuyWepon(pnWepon) == 0) 
							BuyWepon_loaded  = true;
						else
							BuyWepon_loaded = false;

						hideLoadingLabel();
					}


					break;
				case "tabtienich":		// tien ich
									
					break;

				case "tabsms":		// sms
					break;

				case "tabbienche":		// bien che
					cboBienCheCity.Items.Clear();
					cboBienCheCity.Items.AddRange(Command.CityObj.City.AllCity);
					chklstGeneral.Items.Clear();
					LVClient.Common.common.LoadGeneralForBienChe(tvBienCheList);
					btBiencheAccept.Enabled = false;
					break;

				case "tabdieuphai":		// ddieu phai

					cboTabDieuPhaiThanhPhaiQuanVan.Items.Clear();
					cboTabDieuPhaiThanhPhaiQuanVan.Items.AddRange(Command.CityObj.City.AllCity);
					cbTabDieuPhaiThanhPhaiDiLoiDai.Items.Clear();
					cbTabDieuPhaiThanhPhaiDiLoiDai.Items.AddRange(Command.CityObj.City.AllCity);

					btTabDieuPhaiPhaiQuanVan.Enabled = false;
					showDataForGridDieuPhai();
					break;

				case "tabvanchuyenvukhi":

					LoadDataForVCVK();
					Common.common.LoadDataResultForVCVK(lstVCVKResult);
					break;

				case "tabbinhman":
					this.cbTabBinhManThanhXuatQuan.Items.Clear();
					if (LVClient.Command.CityObj.City.AllCity == null)
					{
						LVClient.Command.City.UpdateAllSimpleCity();
					}

					if (LVClient.Command.CityObj.City.AllCity == null) return;


					this.cbTabBinhManThanhXuatQuan.Items.AddRange(LVClient.Command.CityObj.City.AllCity);
					if (this.cbTabBinhManThanhXuatQuan.SelectedItem == null)
					{
						this.chkTabBinhManTuongXuatTran.Items.Clear();
					}
					Common.common.LoadDataResultBinhMan(chkTabBinhManList);
					break;

				case "tabcallman":
					this.cboCallManThanhTraiXuatQuan.Items.Clear();
					if (LVClient.Command.CityObj.City.AllCity == null)
					{
						LVClient.Command.City.UpdateAllSimpleCity();
					}

					if (LVClient.Command.CityObj.City.AllCity == null) return;


					this.cboCallManThanhTraiXuatQuan.Items.AddRange(LVClient.Command.CityObj.City.AllCity);
					if (this.cboCallManThanhTraiXuatQuan.SelectedItem == null)
					{
						this.chklbCallManTuongXuatTran.Items.Clear();
					}
					chklbCallManListResult.Items.Clear();
					chklbCallManListResult.Items.AddRange(CallManList.ToArray());

					break;


			}


		}
		catch (Exception ex)
		{
		}
	}

		private void LoadDataForBinhMan()
		{
			cbTabBinhManThanhXuatQuan.Items.AddRange(Command.CityObj.City.AllCity);


		}
		private void LoadDataForVCVK()
		{
			try
			{

				chklVCVKThanhDi.Items.Clear();
				chklVCVKThanhDen.Items.Clear();
				chklVCVKLoaiVuKhi.Items.Clear();
				for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
				{
					if (Command.CityObj.City.AllCity[i].id > 0)
					{
						chklVCVKThanhDi.Items.Add(Command.CityObj.City.AllCity[i], false);
						chklVCVKThanhDen.Items.Add(Command.CityObj.City.AllCity[i], false);
					}
				}
				chklVCVKLoaiVuKhi.Items.AddRange(Common.Wepons.arWepon);


				/*
				cbVCVKThanhDi.Items.Clear();
				chklVCVKThanhDen.Items.Clear();
				cbVCVKLoaiVK.Items.Clear();
				for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
				{
					if (Command.CityObj.City.AllCity[i].id > 0)
					{
						cbVCVKThanhDi.Items.Add(Command.CityObj.City.AllCity[i]);
						chklVCVKThanhDen.Items.Add(Command.CityObj.City.AllCity[i], false);
					}
				}

				cbVCVKLoaiVK.Items.AddRange(Common.Wepons.arWepon);
				*/

			}
			catch (Exception ex)
			{

			}
		}


		/* public void FirstLogin() {
			 notifyIcon1.Text = "Đang load dữ liệu, vui lòng chờ. Máy có thể đứng đó.";
            
			 if (LVClient.Web.LVWeb.LoginHtml != null) {
				 while (true) {
					 try {
						 Hashtable lastlogindata = Web.ParseHeader.GetDataFromForm(LVClient.Web.LVWeb.LoginHtml);
						 Hashtable lastlogin = Web.LVWeb.LoginPartner(lastlogindata["uid"].ToString(), lastlogindata["uname"].ToString(), lastlogindata["ulgtime"].ToString(), lastlogindata["pid"].ToString(), lastlogindata["sign"].ToString());
						 Web.LVWeb.CurrentLoginInfo = new Web.LoginInfo((string[])lastlogin["Set-Cookie"]);
                        
						 Command.City.GetAllCity();
							
						 Common.common.LoadCityToGridForSellResource(this.dtaSELL);
						 while (true) {
							 try {
								 LoadAvgPrice();
								 break;
							 } catch (Exception ex) {
							 }
						 }
						 Common.common.LoadCityToGridForBuyResource(this.dtaBUYRESOURCE);
						 Common.common.LoadCityToGridForAnUi(dtaAnUi);
						 Common.common.LoadBuildingToTreeViewForbuild(this.tvBUILD);
						 Common.common.LoadBuildingToTreeViewForbuild(this.tvDEL);
						 while (true) {
							 try {
								 Command.Common.GetMaxNhiemVu();
								 break;
							 } catch (Exception ex) {
							 }
						 }
						 Common.common.LoadUpgradeToTreeViewForUpdate(tvUpdate);
						 Common.common.LoadCityToGridForVanchuyen(pnVanchuyen);
						 Common.common.LoadDoanhTraiForMove(pnDoanhTrai);
						 Common.common.LoadGeneralForUpSiKhi(tvSIKHI);
						 Common.common.LoadCityForBuyWepon(pnWepon);



						 chkAutoAll.Enabled = true;
						 IsLogin = true;
						 cboCity.Items.Clear();
						 cboCity.Items.AddRange(Command.CityObj.City.AllCity);
						 cboCityForUpgrade.Items.Clear();
						 cboCityForUpgrade.Items.AddRange(Command.CityObj.City.AllCity);
						 cboNhiemVu.Items.Clear();
						 cboNhiemVu.Items.AddRange(Command.CommonObj.ThaoPhat.AllNhiemVu);
						 notifyIcon1.Text = "LVClient";
						 LVBUILD = new LVClient.LVThread.BUILD(lblBUILDMESSAGE);
						 LVDEL = new LVClient.LVThread.DEL(lblDELMESSAGE);
						 LVSELL = new LVClient.LVThread.SELL(lblSELLMESSAGE);
						 LVBUYRES = new LVClient.LVThread.BUYRES(lblBUYRESMESSAGE);
						 LVTHAOPHAT = new LVClient.LVThread.THAOPHAT(lblTHAOPHATMESSAGE);
						 LVUPGRADE = new LVClient.LVThread.UPGRADE(lblUPGEADEMESSAGE);
						 LVANUI = new LVClient.LVThread.ANUI(lblANUIMESSAGE);
						 LVVANCHUYEN = new LVClient.LVThread.VANCHUYEN(lblVANCHUYENMESSAGE);
						 LVMOVEDOANHTRAI = new LVClient.LVThread.MOVEDOANHTRAI(lblMOVEDOANHTRAI);
						 LVSIKHI = new LVClient.LVThread.SIKHI(lblSIKHIMESSAGE);
						 LVBUYWEPON = new LVClient.LVThread.BUYWEPON(lblBUYWEPONMESSAGE);
						 LVCITYTASK = new LVClient.LVThread.CITYTASK();
						 //LVCITYTASK.IsRun = true;
                        
						 LVCITYTASK.Auto();
                        
						 LVClient.Web.LVWeb.debug = false;
						 LVClient.Web.LVWeb.firstlogin = false;
						 break;
					 } catch (Exception ex) {
						 //MessageBox.Show(ex.ToString());
					 }
				 }
			 } else {
				 Application.Exit();
			 }
		 }

		 */
		private void notifyIcon1_MouseDoubleClick(object sender, MouseEventArgs e) 
		{
            this.Show();
			WindowState = FormWindowState.Normal;

        }

        private void frmmain_Deactivate(object sender, EventArgs e) {
            if (chkAutoAll.Checked) 
			{
               // this.Hide();
				if (WindowState == FormWindowState.Minimized) this.Hide();
            }
        }

        private void deltuong()
        {

        }

        private void chkAutoAll_CheckedChanged(object sender, EventArgs e) 
		{
           
			
			//LVClient.LVThread.AUTOFIGHTING.startBattle(3903, 0, 1, 1000,13);
			//notifyIcon1.ShowBalloonTip(3000, "", "text..", ToolTipIcon.None);
			//string message = "Hi " + LVClient.Web.LVWeb.lvusername + "!!!\r\n" + DanhTuongDangViengTham;
			//string message = "Hi " + LVClient.Web.LVWeb.lvusername + "!!!\r\n Có danh tướng viếng thăm nè";
			//string title = "Hi " + LVClient.Web.LVWeb.lvusername + "!!!";
			//notifyIcon1.ShowBalloonTip(3000, "", message, ToolTipIcon.None);


			//Command.CityObj.City city = Command.City.GetCityInfo(28200);		//iwunu13
			//city = Command.City.GetCityInfo(52501);			//D2A | JUN

			//tmAuto.Enabled = chkAutoAll.Checked;

			chkAutoBuild.Enabled = chkAutoAll.Checked;
            chkAutoBuyResource.Enabled = chkAutoAll.Checked;
            chkAutoSellFood.Enabled = chkAutoAll.Checked;
            chkAutoST.Enabled = chkAutoAll.Checked;
            chkAutoUpgrade.Enabled = chkAutoAll.Checked;
            chkAutoUpDanSo.Enabled = chkAutoAll.Checked;
            chkAutoVanchuyen.Enabled = chkAutoAll.Checked;
            chkAutoMove.Enabled = chkAutoAll.Checked;
            chkAutoUpSiKhi.Enabled = chkAutoAll.Checked;
            chkAutobuyWepon.Enabled = chkAutoAll.Checked;
            chkAutoDel.Enabled = chkAutoAll.Checked;
			chkAutoBienche.Enabled = chkAutoAll.Checked;
			chkAutoDieuPhai.Enabled = chkAutoAll.Checked;
			chkAUTOVCVK.Enabled = chkAutoAll.Checked;
			chkAUTOBINHMAN.Enabled = chkAutoAll.Checked;
			chkAUTOCALLMAN.Enabled = chkAutoAll.Checked;

			/*
			if (!chkAutoAll.Checked)
			{
				chkAutoBuild.Checked = chkAutoAll.Checked;
				chkAutoBuyResource.Checked = chkAutoAll.Checked;
				chkAutoSellFood.Checked = chkAutoAll.Checked;
				chkAutoST.Checked = chkAutoAll.Checked;
				chkAutoUpgrade.Checked = chkAutoAll.Checked;
				chkAutoUpDanSo.Checked = chkAutoAll.Checked;
				chkAutoVanchuyen.Checked = chkAutoAll.Checked;
				chkAutoMove.Checked = chkAutoAll.Checked;
				chkAutoUpSiKhi.Checked = chkAutoAll.Checked;
				chkAutobuyWepon.Checked = chkAutoAll.Checked;
				chkAutoDel.Checked = chkAutoAll.Checked;
				chkAutoBienche.Checked = chkAutoAll.Checked;
				chkAutoDieuPhai.Checked = chkAutoAll.Checked;
				chkAUTOVCVK.Checked = chkAutoAll.Checked;
				chkAUTOBINHMAN.Checked = chkAutoAll.Checked;
			}
			*/

			if (!chkAutoAll.Checked)
			{
				stopAllThread();
			}
			else
			{
				if (!LVAUTOTASK.IsRun) LVAUTOTASK.Auto();
				if (!LVCITYTASK.IsRun) LVCITYTASK.Auto();
			}

        }

        private void cmdGet_Click(object sender, EventArgs e) {
            Command.OPT.BuyItem(1);
        }

        private void cboCity_SelectedIndexChanged(object sender, EventArgs e) {
            cboGeneral.Items.Clear();
            try {
				showLoadingLabel();
				LVClient.Command.Common.GetGeneral(cboCity.SelectedIndex, false); 
				cboGeneral.Items.AddRange(Command.CityObj.City.AllCity[cboCity.SelectedIndex].MilitaryGeneral);

				int g;
				for (int i = 0; i < cboGeneral.Items.Count; i++)
				{
					g = ((Command.CityObj.MilitaryGeneral)cboGeneral.Items[i]).GeneralId;
					for (int k = 0; k < TuongDiThaoPhatList.Count; k++)
					{
						if (g == ((Common.GeneralThaoPhat)TuongDiThaoPhatList[k]).GeneralId )
							cboGeneral.SetItemChecked(i, true);
					}
				}

				hideLoadingLabel();
            } catch (Exception ex) { }
        }

        private void LoadAvgPrice() 
		{
            /* 1. Lúa
             2. Gỗ
             3. Đá
             4. Sắt
             * */
            //txtPRICELUA.Text = "" + (int.Parse(Command.OPT.AvgPrice(1).ToString())+10);
            //txtPRICEGO.Text = "" + (int.Parse(Command.OPT.AvgPrice(2).ToString()) + 10);
            //txtPRICEDA.Text = "" + (int.Parse(Command.OPT.AvgPrice(3).ToString()) + 10);
            //txtPRICESAT.Text = "" + (int.Parse(Command.OPT.AvgPrice(4).ToString()) + 10);
        }

        private void cmdLoadConfig_Click(object sender, EventArgs e) {
            openFileDialog1.ShowDialog();
			
			(new LVClient.Web.SaveNLoad()).loadConfig(fileSavepath);

        }

        private void openFileDialog1_FileOk(object sender, CancelEventArgs e) {

			fileSavepath = openFileDialog1.FileName;
			return;
			 /*
			Common.config.load(openFileDialog1.FileName);
            try {
                //Load ban tai nguyen
                if (Common.config.SELLRESOURCE != null) {
                    txtSELLCHECK.Text = Common.config.SELLRESOURCE[1];
                    //nap lua
                    txtCOUNTLUA.Text = Common.config.SELLRESOURCE[2];
                    txtPRICELUA.Text = Common.config.SELLRESOURCE[3];
                    txtSAFELUA.Text = Common.config.SELLRESOURCE[4];
                    //nap go
                    txtCOUNTGO.Text = Common.config.SELLRESOURCE[5];
                    txtPRICEGO.Text = Common.config.SELLRESOURCE[6];
                    txtSAFEGO.Text = Common.config.SELLRESOURCE[7];
                    //nap sat
                    txtCOUNTSAT.Text = Common.config.SELLRESOURCE[8];
                    txtPRICESAT.Text = Common.config.SELLRESOURCE[9];
                    txtSAFESAT.Text = Common.config.SELLRESOURCE[10];
                    //nap da
                    txtCOUNTDA.Text = Common.config.SELLRESOURCE[11];
                    txtPRICEDA.Text = Common.config.SELLRESOURCE[12];
                    txtSAFEDA.Text = Common.config.SELLRESOURCE[13];
                    //nap thanh
                    DataTable data = (DataTable)dtaSELL.DataSource;
                    for (int i = 0; i < data.Rows.Count; i++) {
                        for (int j = 14; j < Common.config.SELLRESOURCE.Length; j++) {
                            if (Common.config.SELLRESOURCE[j] == data.Rows[i]["ID_TT"].ToString()) {
                                data.Rows[i]["SELL_LUA"] = Common.config.SELLRESOURCE[j + 1] == "1" ? true : false;
                                data.Rows[i]["SELL_GO"] = Common.config.SELLRESOURCE[j + 2] == "1" ? true : false;
                                data.Rows[i]["SELL_SAT"] = Common.config.SELLRESOURCE[j + 3] == "1" ? true : false;
                                data.Rows[i]["SELL_DA"] = Common.config.SELLRESOURCE[j + 4] == "1" ? true : false;
                            }
                            j += 4;
                        }
                    }
                }
                //Load mua tai nguyen
                if (Common.config.BUYRESOURCE != null) {
                    txtBUYRESOURCECHECK.Text = Common.config.BUYRESOURCE[1];
                    txtSAFEGOLD.Text = Common.config.BUYRESOURCE[2];
                    DataTable data = (DataTable)dtaBUYRESOURCE.DataSource;
                    for (int i = 0; i < data.Rows.Count; i++) {
                        for (int j = 3; j < Common.config.BUYRESOURCE.Length; j++) {
                            if (Common.config.BUYRESOURCE[j] == data.Rows[i]["ID_TT"].ToString()) {
                                data.Rows[i]["BUY_LUA"] = Common.config.BUYRESOURCE[j + 1] == "1" ? true : false;
                                data.Rows[i]["BUY_GO"] = Common.config.BUYRESOURCE[j + 2] == "1" ? true : false;
                                data.Rows[i]["BUY_SAT"] = Common.config.BUYRESOURCE[j + 3] == "1" ? true : false;
                                data.Rows[i]["BUY_DA"] = Common.config.BUYRESOURCE[j + 4] == "1" ? true : false;
                            }
                            j += 4;
                        }
                    }
                }
                //load xay nha
                if (Common.config.UPDATEBUILDING != null) {
                    txtBUILDCHECK.Text = Common.config.UPDATEBUILDING[1];
                    TreeNode root = tvBUILD.Nodes["root"];
                    for (int i = 2; i < Common.config.UPDATEBUILDING.Length; i++) {
                        if (Common.config.UPDATEBUILDING[i] == root.Name) root.Checked = true;
                    }
                    foreach (TreeNode tt in root.Nodes) {
                        for (int i = 2; i < Common.config.UPDATEBUILDING.Length; i++) {
                            if (Common.config.UPDATEBUILDING[i] == tt.Name) tt.Checked = true;
                        }
                        foreach (TreeNode b in tt.Nodes) {
                            for (int i = 2; i < Common.config.UPDATEBUILDING.Length; i++) {
                                if (Common.config.UPDATEBUILDING[i] == b.Name) b.Checked = true;
                            }
                        }
                    }
                }
                //load ha nha
                if (Common.config.DELBUILDING != null) {
                    txtDELCHECK.Text = Common.config.DELBUILDING[1];
                    TreeNode root = tvDEL.Nodes["root"];
                    for (int i = 2; i < Common.config.DELBUILDING.Length; i++) {
                        if (Common.config.DELBUILDING[i] == root.Name) root.Checked = true;
                    }
                    foreach (TreeNode tt in root.Nodes) {
                        for (int i = 2; i < Common.config.DELBUILDING.Length; i++) {
                            if (Common.config.DELBUILDING[i] == tt.Name) tt.Checked = true;
                        }
                        foreach (TreeNode b in tt.Nodes) {
                            for (int i = 2; i < Common.config.DELBUILDING.Length; i++) {
                                if (Common.config.DELBUILDING[i] == b.Name) b.Checked = true;
                            }
                        }
                    }
                }
                //load vu khi
                if (Common.config.WEPON != null) {
                    txtCHECKWEPON.Text = Common.config.WEPON[1];
                    txtCOUNTWEPON.Text = Common.config.WEPON[2];
                    for (int i = 3; i < Common.config.WEPON.Length; i++) {
                        foreach (object o in pnWepon.Controls) {
                            Command.OPTObj.wepon w = (Command.OPTObj.wepon)o;
                            if (w.cityid.ToString() == Common.config.WEPON[i].ToString()) {
                                w.cboWepon.Text = Common.config.WEPON[i + 1];
                                w.cboAmor.Text = Common.config.WEPON[i + 2];
                                w.cboHorse.Text = Common.config.WEPON[i + 3];
                                w.cboLevel.Text = Common.config.WEPON[i + 4];
                                w.chkOK.Checked = bool.Parse(Common.config.WEPON[i + 5]);
                                i = i + 5;
                            }
                        }
                    }
                }
            } catch (Exception ex) {
            }
			  * */
        }

        private void cmdSaveConfig_Click(object sender, EventArgs e) {
            saveFileDialog1.ShowDialog();
			(new LVClient.Web.SaveNLoad()).saveConfig(fileSavepath);
        }

        private void saveFileDialog1_FileOk(object sender, CancelEventArgs e) 
		{
			
			// code moi
			fileSavepath = saveFileDialog1.FileName;			
			return;

		   /*
			// code cu, khong dung den
            try {
                File.Delete(saveFileDialog1.FileName);
            } catch (Exception ex) {
            }
            try {
                FileStream f = new FileStream(saveFileDialog1.FileName, FileMode.CreateNew);
                string data = "";

				//luu xay nha
				data += "UPDATEBUILDING,";
				data += txtBUILDCHECK.Text + ",";				//thoigian
				TreeNode root = tvBUILD.Nodes["root"];
				if (root.Checked == true) data += root.Name + ",";
				foreach (TreeNode tt in root.Nodes)
				{
					if (tt.Checked == true) data += tt.Name + ",";
					foreach (TreeNode b in tt.Nodes)
					{
						if (b.Checked == true) data += b.Name + ",";
					}
				}

				
				//luu sell
                data += "/SELLRESOURCE,";
                data += txtSELLCHECK.Text+",";

                data += txtCOUNTLUA.Text + ",";
                data += txtPRICELUA.Text + ",";
                data += txtSAFELUA.Text + ",";

                data += txtCOUNTGO.Text + ",";
                data += txtPRICEGO.Text + ",";
                data += txtSAFEGO.Text + ",";

                data += txtCOUNTSAT.Text + ",";
                data += txtPRICESAT.Text + ",";
                data += txtSAFESAT.Text + ",";

                data += txtCOUNTDA.Text + ",";
                data += txtPRICEDA.Text + ",";
                data += txtSAFEDA.Text + ",";
                DataTable grid = (DataTable)dtaSELL.DataSource;
                for (int i = 0; i < grid.Rows.Count; i++) {
                    data += grid.Rows[i]["ID_TT"].ToString() + ",";
                    data += (bool)grid.Rows[i]["SELL_LUA"]==true?"1,":"0,";
                    data += (bool)grid.Rows[i]["SELL_GO"] == true ? "1," : "0,";
                    data += (bool)grid.Rows[i]["SELL_SAT"] == true ? "1," : "0,";
                    data += (bool)grid.Rows[i]["SELL_DA"] == true ? "1," : "0,";
                }
                //luu buy
                data += "/BUYRESOURCE,";
                data += txtBUYRESOURCECHECK.Text + ",";
                data += txtSAFEGOLD.Text + ",";

                grid = (DataTable)dtaBUYRESOURCE.DataSource;
                for (int i = 0; i < grid.Rows.Count; i++) {
                    data += grid.Rows[i]["ID_TT"].ToString() + ",";
                    data += (bool)grid.Rows[i]["BUY_LUA"] == true ? "1," : "0,";
                    data += (bool)grid.Rows[i]["BUY_GO"] == true ? "1," : "0,";
                    data += (bool)grid.Rows[i]["BUY_SAT"] == true ? "1," : "0,";
                    data += (bool)grid.Rows[i]["BUY_DA"] == true ? "1," : "0,";
                }

                //luu ha nha
                data += "/DELBUILDING,";
                data += txtDELCHECK.Text + ",";
                root = tvDEL.Nodes["root"];
                if (root.Checked == true) data += root.Name + ",";
                foreach (TreeNode tt in root.Nodes) {
                    if (tt.Checked == true) data += tt.Name + ",";
                    foreach (TreeNode b in tt.Nodes) {
                        if (b.Checked == true) data += b.Name + ",";
                    }
                }
                
                //thao phat
                data += "/WEPON,";
                data += txtCHECKWEPON.Text + ",";
                data += txtCOUNTWEPON.Text + ",";
                foreach (object c in pnWepon.Controls) {
                    LVClient.Command.OPTObj.wepon w = (LVClient.Command.OPTObj.wepon)c;
                    data += w.cityid + "," + w.cboWepon.Text + "," + w.cboAmor.Text + "," + w.cboHorse.Text + "," + w.cboLevel.Text + "," + w.chkOK.Checked.ToString() + ",";
                }

                f.Write(UTF8Encoding.UTF8.GetBytes(data), 0, UTF8Encoding.UTF8.GetBytes(data).Length);
                f.Flush();
                f.Close();
            } catch (Exception ex) {
            }
		    */ 
        }

        private void cmdUpdatePrice_Click(object sender, EventArgs e) {
            
        }

        private void chkAutoBuild_CheckedChanged(object sender, EventArgs e) {
			try
			{
				if (chkAutoBuild.Checked)
				{
					if (!LVClient.Command.CityObj.City.isBuildAll)
					{
						bool hasUp = false;
						for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
						{
							if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding != null)
							{
								for (int j = 0; j < LVClient.Command.CityObj.City.AllCity[i].AllBuilding.Length; j++)
								{
									if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j].isUp)
									{
										hasUp = true;
										break;
									}
								}

								if (hasUp) break;
							}
						}

						if (!hasUp)
						{
							lblBUILDMESSAGE.Text = "Không có nhà nào để xây cả, kiểm tra lại đê";
							pnXayNha.Enabled = true; ;
                            chkAutoBuild.Checked = false;
                            return;
						}
					}
					LVBUILD.GetParameter(int.Parse(txtBUILDCHECK.Text) * 60 * 1000);
					tvBUILD.Enabled = false;
					pnXayNha.Enabled = false;
					cmdReloadBuilding.Enabled = false;
					//LVBUILD.run();
					LVBUILD.Auto();
				}
				else
				{
                    tvBUILD.Enabled = true;
                    //cmdReloadBuilding.Enabled = true;
                    pnXayNha.Enabled = true; ;
                    LVBUILD.Stop();
				}
			}
			catch (Exception ex)
			{
				lblBUILDMESSAGE.Text = "Chưa chọn đúng tham số";
				pnXayNha.Enabled = true; ;
                chkAutoBuild.Checked = false;
            }

        }

        private void frmmain_FormClosing(object sender, FormClosingEventArgs e) 
		{

			string message =  "Hi " + LVClient.Web.LVWeb.lvusername + "!!!\r\n Bạn không muốn chạy chương trình này nữa phải không?";
			string caption = "Chán quá, chuồn thôi  " + LVClient.Web.LVWeb.lvusername;

			MessageBoxButtons buttons = MessageBoxButtons.YesNo;
			DialogResult result;

			// Displays the MessageBox.
			result = MessageBox.Show(message, caption, buttons, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);

			if(result == DialogResult.Yes)
			{
				stopAllThread();
				// Closes the parent form.
				//this.Close();
				e.Cancel = false;	

			}
			else
			{
				e.Cancel = true;				
			}
        }

        private void chkAutoSellFood_CheckedChanged(object sender, EventArgs e) {
            try
			{
				if (chkAutoSellFood.Checked) {
                /*
					LVSELL.GetParameter(
                    int.Parse(txtCOUNTLUA.Text),
                    int.Parse(txtPRICELUA.Text),
                    int.Parse(txtSAFELUA.Text),
                    int.Parse(txtCOUNTGO.Text),
                    int.Parse(txtPRICEGO.Text),
                    int.Parse(txtSAFEGO.Text),
                    int.Parse(txtCOUNTDA.Text),
                    int.Parse(txtPRICEDA.Text),
                    int.Parse(txtSAFEDA.Text),
                    int.Parse(txtCOUNTSAT.Text),
                    int.Parse(txtPRICELSAT.Text),
                    int.Parse(txtSAFESAT.Text),
                    dtaSELL, int.Parse(txtSELLCHECK.Text) * 60 * 1000);
				 
				 */

					LVSELL.GetParameter(BanTaiNguyen, int.Parse(txtSELLCHECK.Text) * 60 * 1000);
                
				pnSELL.Enabled = false;
                LVSELL.Auto();
            } else {
                LVSELL.Stop();
                pnSELL.Enabled = true;
            }
			}
			catch (Exception ex)
			{
				lblSELLMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAutoSellFood.Checked = false;
			}
        }

        private void chkAutoBuyResource_CheckedChanged(object sender, EventArgs e) {
            try
			{
			if (chkAutoBuyResource.Checked) 
			{
                //LVBUYRES.GetParameter(
                //    int.Parse(txtSAFEGOLD.Text),
                //    dtaBUYRESOURCE, int.Parse(txtBUYRESOURCECHECK.Text) * 60 * 1000);

				LVBUYRES.GetParameter(MuaTaiNguyen);
				pnLVBUYRES.Enabled = false;
				
                LVBUYRES.Auto();
            } else {
                LVBUYRES.Stop();
                pnLVBUYRES.Enabled = true;
            }
			}
			catch (Exception ex)
			{
				lblBUYRESMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAutoBuyResource.Checked = false;
			}

        }

        private void chkAutoST_CheckedChanged(object sender, EventArgs e) {
            if (chkAutoST.Checked) 
			{
				try
				{

					//-- phan nay chua check
				 /*
					LVTHAOPHAT.GetParameter(
                        TuongDiThaoPhat.cityid , TuongDiThaoPhat.general1, TuongDiThaoPhat.general2, TuongDiThaoPhat.general3, 
						TuongDiThaoPhat.general4, TuongDiThaoPhat.general5,
                        TuongDiThaoPhat.nhiemvuid,
                        TuongDiThaoPhat.tuupsikhi,
                        TuongDiThaoPhat.timetorun* 60 * 1000, 
						TuongDiThaoPhat.sikhimin,
						TuongDiThaoPhat.soluongquanmin,
						TuongDiThaoPhat.tubienchequan
                    );
					*/

					LVTHAOPHAT.GetParameter(TuongDiThaoPhatList, int.Parse((txtTPCHECK.Text)) * 60 * 1000);

				 


                    pnTHAOPHAT.Enabled = false;
					LVTHAOPHAT.Auto();

				
				} 
			    catch (Exception ex) 
				{
                    lblTHAOPHATMESSAGE.Text = "Chưa chọn đúng tham số";
                    chkAutoST.Checked = false;
                }
            } 
		    else 
	        {
                LVTHAOPHAT.Stop();
                pnTHAOPHAT.Enabled = true;
            }
        }

        private void chkAutoUpgrade_CheckedChanged(object sender, EventArgs e) {
            if (chkAutoUpgrade.Checked) 
			{
                try 
				{
                   
					//LVUPGRADE.GetParameter(tvUpdate, ((LVClient.Command.CityObj.City)cboCityForUpgrade.SelectedItem).id, 
					//	int.Parse(txtCHECKUPDATE.Text) * 60 * 1000);

					int cityid = int.Parse(UpgradeForAuto[0].ToString()); ;
					int citypos = LVClient.Command.City.GetCityPostByID(cityid);
					if (citypos == -1)
					{
						lblUPGEADEMESSAGE.Text = "Chưa chọn thành chính";
						chkAutoUpgrade.Checked = false;
						return;
					}

					LVUPGRADE.GetParameter(UpgradeForAuto,	int.Parse(txtCHECKUPDATE.Text.Trim()) * 60 * 1000);
					string str = txtCHECKUPDATE.Text; 											  					
					pnUPGRADE.Enabled = false;
                    LVUPGRADE.Auto();
                } 
				catch (Exception ex) 
				{
                    lblUPGEADEMESSAGE.Text = "Chưa chọn thành chính";
                    chkAutoUpgrade.Checked = false;
                }
            } else {
                LVUPGRADE.Stop();
                pnUPGRADE.Enabled = true;
            }
        }

        private void chkAutoUpDanSo_CheckedChanged(object sender, EventArgs e) {
			try
			{
			if (chkAutoUpDanSo.Checked) 
			{
                //LVANUI.GetParameter(dtaAnUi, int.Parse(txtCHECKANUI.Text) * 60 * 1000);
                //dtaAnUi.Enabled = false;

				//LVANUI.GetParameter(dtaAnUi, int.Parse(txtCHECKANUI.Text) * 60 * 1000);
				//dtaAnUi.Enabled = false;
				//LVANUI.GetParameter(AnuiForAuto, int.Parse(txtCHECKANUI.Text) * 60 * 1000);
				LVANUI.GetParameter(AnuiForAuto, chkANUI_TuMuaLua.Checked, long.Parse(txtANUI_VangAnToan.Text), int.Parse(txtCHECKANUI.Text) * 60 * 1000);
				chklstAnUi.Enabled = false;
				LVANUI.Auto();

				//LVANUI.run();

            } else {
                LVANUI.Stop();
                //dtaAnUi.Enabled = true;
				chklstAnUi.Enabled = true;
            }
			}
			catch (Exception ex)
			{
				lblANUIMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAutoUpDanSo.Checked = false;
			}
        }

        private void chkAutoVanchuyen_CheckedChanged(object sender, EventArgs e) {
            try {
			if (chkAutoVanchuyen.Checked) {
                LVVANCHUYEN.GetParameter(pnVanchuyen, int.Parse(txtCHECKVANCHUYEN.Text) * 60 * 1000);
                pnVanchuyen.Enabled = false;
                LVVANCHUYEN.Auto();
            } else {
                LVVANCHUYEN.Stop();
                pnVanchuyen.Enabled = true;
            }
			}
			catch (Exception ex)
			{
				lblVANCHUYENMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAutoVanchuyen.Checked = false;
			}
        }

		private void chkAutoMove_CheckedChanged(object sender, EventArgs e)
		{
			try
			{

				if (chkAutoMove.Checked)
				{
					//LVMOVEDOANHTRAI.GetParameter(pnDoanhTrai, int.Parse(txtCHECKMOVE.Text) * 60 * 1000);
					if (DiChuyenTrai.Count > 0)
					{
						LVMOVEDOANHTRAI.GetParameter(DiChuyenTrai, int.Parse(txtCHECKMOVE.Text) * 60 * 1000);
						pnDoanhTrai.Enabled = false;
						LVMOVEDOANHTRAI.Auto();
					}
					else
					{
						lblMOVEDOANHTRAI.Text = "Chưa chọn đúng tham số";
						chkAutoMove.Checked = false;
					}
				}
				else
				{
					LVMOVEDOANHTRAI.Stop();
					pnDoanhTrai.Enabled = true;
				}
			}
			catch (Exception ex)
			{
				lblMOVEDOANHTRAI.Text = "Chưa chọn đúng tham số";
				chkAutoMove.Checked = false;
			}
		}

        private void tvBUILD_AfterSelect(object sender, TreeViewEventArgs e) {

        }

        private void tvBUILD_AfterCheck(object sender, TreeViewEventArgs e) {
            foreach (TreeNode c in e.Node.Nodes) 
            {
                c.Checked = e.Node.Checked;
            }
        }

        private void chkAutoUpSiKhi_CheckedChanged(object sender, EventArgs e) 
		{
			try
			{
				if (chkAutoUpSiKhi.Checked) 
				{
					LVSIKHI.GetParameter(tvSIKHI,int.Parse(txtOneSiKhi.Text), int.Parse(txtCHECKSIKHI.Text) * 60 * 1000);
					tvSIKHI.Enabled = false;
					LVSIKHI.Auto();
				} else {
					LVSIKHI.Stop();
					tvSIKHI.Enabled = true;
				}
			}
			catch (Exception ex)
			{
				lblSIKHIMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAutoUpSiKhi.Checked = false;
			}
        }

        private void chkAutobuyWepon_CheckedChanged(object sender, EventArgs e) 
		{
			try
			{
				if (chkAutobuyWepon.Checked) 
				{
					LVBUYWEPON.GetParameter(int.Parse(txtCOUNTWEPON.Text),pnWepon, int.Parse(txtCHECKWEPON.Text) * 60 * 1000);
					pnWepon.Enabled = false;
					LVBUYWEPON.Auto();
				} else 
				{
					LVBUYWEPON.Stop();
					pnWepon.Enabled = true;
				}
			}
			catch (Exception ex)
			{
				lblBUYWEPONMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAutobuyWepon.Checked = false;
         
			}

        }

        private void cmdUpdatePrice_Click_1(object sender, EventArgs e) {
            //LVThread.UPDATEPRICE up = new LVClient.LVThread.UPDATEPRICE(int.Parse(txtPRICELUA.Text), int.Parse(txtPRICEGO.Text), int.Parse(txtPRICEDA.Text), int.Parse(txtPRICESAT.Text));

			LVThread.UPDATEPRICE up = new LVClient.LVThread.UPDATEPRICE(int.Parse(txtBanTN_LUA_TB_Heso.Text), int.Parse(txtBanTN_GO_TB_Heso.Text), 
												int.Parse(txtBanTN_DA_TB_Heso.Text), int.Parse(txtBanTN_SAT_TB_Heso.Text));
			up.Auto();
        }

        private void chkDebug_CheckedChanged(object sender, EventArgs e) {
            lock (LVClient.Web.LVWeb.islock) {
                LVClient.Web.LVWeb.debug = chkDebug.Checked;
            }
        }

        private void cmdBanthuong_Click(object sender, EventArgs e) 
		{
            LVThread.BANTHUONG bt = new LVClient.LVThread.BANTHUONG(true);

            bt.Auto();
        }

        private void checkBox1_CheckedChanged(object sender, EventArgs e) {

        }

        private void checkBox2_CheckedChanged(object sender, EventArgs e) {
            lock (LVClient.Web.LVWeb.islock) {
                lock (LVClient.Web.LVWeb.ispause) {
                    LVClient.Web.LVWeb.issendsms = checkBox2.Checked;
                    LVClient.Web.LVWeb.smsusername = txtPhoneSend.Text;
                    LVClient.Web.LVWeb.smspass = txtPassword.Text;
                    LVClient.Web.LVWeb.smsto = txtTo.Text;
                }
            }
        }

        private void cmdTestSMS_Click(object sender, EventArgs e) {
            LVClient.Web.LVWeb.LoginMobi(txtPhoneSend.Text, txtPassword.Text, txtTo.Text, "Test thu tinh nang send sms");
        }

        private void timer1_Tick(object sender, EventArgs e) 
		{
			//System.Collections.ArrayList arTemp = LVClient.Common.ThreadManager.s_alRegister;
			//System.Collections.ArrayList arTempRunning = LVClient.Common.ThreadManager.s_funcRunning;
        }

        private void cboServer_SelectedIndexChanged(object sender, EventArgs e)
        {
            LVClient.Web.LVWeb.Server = int.Parse(cboServer.Text.Substring(0,1));
        }


		private bool ValidateLoginForm()
		{
			if (txtUsername.Text.Trim() == "")
			{
				MessageBox.Show("Chưa nhập Username!");
				return false;
			}
			if (txtLvPassword.Text.Trim() == "")
			{
				MessageBox.Show("Chưa nhập password!");
				return false;
			}


			ProxyProtocol = cbProxyProtocol.SelectedItem.ToString().Trim();

			ProxyServer = txtProxyServer.Text.Trim();
			ProxyPort	= txtProxyPort.Text.Trim();
			ProxyUser	= txtProxyUser.Text.Trim();
			ProxyPass	= txtProxyPassword.Text.Trim();

			if (ProxyProtocol != "NONE")
			{
				if (ProxyServer == "")
				{
					MessageBox.Show("Chưa nhập proxy server!");
					return false;
				}

				if (ProxyPort == "")
				{
					MessageBox.Show("Chưa nhập proxy port!");
					return false;
				}
			}

			switch (ProxyProtocol)
			{

				case "NONE":
					ProxyServer = "";
					ProxyPort = "";
					ProxyUser = "";
					ProxyPass = "";
					break;

				case "HTTP":
				
					ProxyUser = "";
					ProxyPass = "";
					break;
				case "SOCKS4":
					ProxyPass = "";
					break;

				case "SOCKS4a":
					ProxyPass = "";
					break;

				case "SOCKS5":
					break;


			}
			return true;
		}

        private void cmdLogin_Click(object sender, EventArgs e)
        {


	/*		frmLoading frLoading = new frmLoading("Login......");
			frLoading.ShowIcon = false; ;
			frLoading.Activate();
			frLoading.ShowIcon = false;
			frLoading.ShowInTaskbar = false;
			frLoading.TopMost = true;
			frLoading.Show();

		//	showLoading();

	*/
			try
			{
				int count =0;
				Hashtable temp = null;
				Hashtable loginform;
				Hashtable logindata;
				string data;
				int i = 0;

				if (!ValidateLoginForm()) return;

				do
				{
					cmdLogin.Enabled = false;
					showLoadingLabel("Login...");
					try
					{
						 loginform = LVClient.Web.LVWeb.LoginForm();
						//ChallengeScript":"eval(\u0027835+409\u0027)
						//calculate antibot
						data = loginform["DATA"].ToString();
						i = data.IndexOf("\\u0027");
						int j = data.IndexOf("\\u0027", i + 1);
						string[] oper = data.Substring(i + 6, (j - i) - 6).Split(new char[] { '+' });
						int antibot = int.Parse(oper[0].Trim()) + int.Parse(oper[1].Trim());
						logindata = Web.ParseHeader.GetDataFromForm(data);
						logindata["NoBot1$NoBot1_NoBotExtender_ClientState"] = antibot.ToString();
						logindata["TxtPass"] = txtLvPassword.Text;
						logindata["TxtUserName"] = txtUsername.Text;
						logindata.Remove("imgLoginLogOut");
						logindata["imgLoginLogOut.x"] = 10;
						logindata["imgLoginLogOut.y"] = 10;
						LVClient.Web.LVWeb.LoginFormData = logindata;
						LVClient.Web.LVWeb.lvusername = txtUsername.Text;
						LVClient.Web.LVWeb.lvpassword = txtLvPassword.Text;
						temp = LVClient.Web.LVWeb.Login();
						count++;
					}
					catch (Exception ex)
					{
						count++;
					}
				} while (temp == null && count < 3);

				
				if (temp == null)
				{
					i = 0;
				}
				else
				{
					data = temp["DATA"].ToString();
					i = data.IndexOf("\\u0027");
				}

				if (i > -1)
				{
					hideLoadingLabel();
					cmdLogin.Enabled = true; ;
					MessageBox.Show("Sai pass hoặc đăng nhập thất bại. hê hê");
				}
				else
				{
					temp = LVClient.Web.LVWeb.LoginPlay();
					LVClient.Web.LVWeb.LoginHtml = temp["DATA"].ToString();
					if (!FirstLogin_())
					{
						MessageBox.Show("Sai pass hoặc đăng nhập thất bại. hê hê");
						cmdLogin.Enabled = true; ;
						return;
					}
					txtLvPassword.Enabled = false;
					txtUsername.Enabled = false;
					cmdLogin.Enabled = false;
					//frLoading.Close();

					ShowCoDanhTuongViengTham();
					hideLoadingLabel();
					MessageBox.Show("Đã login thành công. Hãy quên phần login đi nhé. Auto thôi.");

					this.Text = strVersion + " - Welcome " + LVClient.Web.LVWeb.lvusername;

					notifyIcon1.Text = strVersion + " - " + LVClient.Web.LVWeb.lvusername;
					//LVClient.Web.LVWeb.processCheckImage();


					
				}
			}
			catch
			{
				MessageBox.Show("Hic hic, không login được mà không biết tại sao, có thể do mạng lởm. Cố thử lại lần nữa xem sao.", "Lỗi rồi", MessageBoxButtons.OK, MessageBoxIcon.Error);
				txtLvPassword.Enabled = true;
				txtUsername.Enabled = true;
				cmdLogin.Enabled = true;
				//frLoading.Close();
				hideLoadingLabel();
			}
        }

        private void cmdReloadBuilding_Click(object sender, EventArgs e) 
		{
            //Common.common.LoadBuildingToTreeViewForbuild(this.tvBUILD);

            if (cboXayDungCity.SelectedIndex < 0)
            {
                //MessageBox.Show("Chưa chọn thành");
                //cmdReloadBuilding.Enabled = false;

                LVClient.Command.City.UpdateAllSimpleCity();
                cboXayDungCity.Items.Clear();
                cboXayDungCity.Items.AddRange(Command.CityObj.City.AllCity);

            }
            else
            {
                LVClient.Command.City.UpdateAllBuilding(cboXayDungCity.SelectedIndex);
                LVClient.Common.common.LoadBuildingToTreeViewForbuild_(tvBUILD, cboXayDungCity.SelectedIndex);
            }
        }

        private void cmdReload_Click(object sender, EventArgs e) {
            lock (LVClient.Web.LVWeb.islock) {
                //FirstLogin();
				FirstLogin_();
                MessageBox.Show("Đã nạp lại thông tin thành công. Bạn tự load lại cấu hình nhé.");
            }
        }

        private void chkAutoDel_CheckedChanged(object sender, EventArgs e) 
		{
            if (chkAutoDel.Checked) 
			{
                LVDEL.GetParameter(tvDEL, int.Parse(txtDELCHECK.Text) * 60 * 1000);
                tvDEL.Enabled = false;
                LVDEL.Auto();
            } else {
                LVDEL.Stop();
                tvDEL.Enabled = true;
            }
        }

		public void showLoadingLabel(string message)
		{
			lblPanelLoading.Text = message;
			panelLoading.BringToFront();
			panelLoading.Visible = true;
			lblPanelLoading.BringToFront();
			LVFRMMAIN.Refresh();
		}
		public void showLoadingLabel()
		{
			//lblLoading.Location = new Point(LVFRMMAIN.Width / 2 - lblLoading.Width / 2, LVFRMMAIN.Height / 2 - lblLoading.Height);
			lblPanelLoading.Text = "Loading...";
			panelLoading.BringToFront();
			panelLoading.Visible = true;
			lblPanelLoading.BringToFront();
			LVFRMMAIN.Refresh();
			//this.Parent.Refresh();
			this.Refresh();
		}

		public void hideLoadingLabel()
		{
			panelLoading.Visible = false;
			LVFRMMAIN.Refresh();
		}

		public void stopAllThread()
		{

			try {
                if (LVBUILD.IsRun) {
                    LVBUILD.Stop();
                }

				if (LVDEL.IsRun) LVDEL.Stop();

                if (LVSELL.IsRun) {
                    LVSELL.Stop();
                }
                if (LVBUYRES.IsRun) {
                    LVBUYRES.Stop();
                }
                if (LVTHAOPHAT.IsRun) {
                    LVTHAOPHAT.Stop();
                }
                if (LVUPGRADE.IsRun) {
                    LVUPGRADE.Stop();
                }
                if (LVANUI.IsRun) {
                    LVANUI.Stop();
                }
                if (LVVANCHUYEN.IsRun) {
                    LVVANCHUYEN.Stop();
                }
                if (LVMOVEDOANHTRAI.IsRun) {
                    LVMOVEDOANHTRAI.Stop();
                }
                if (LVSIKHI.IsRun) {
                    LVSIKHI.Stop();
                }
                if (LVBUYWEPON.IsRun) {
                    LVBUYWEPON.Stop();
                }
               
                if (LVCITYTASK.IsRun) 
				{
                    LVCITYTASK.Stop();
                }

				if (LVBIENCHE.IsRun) LVBIENCHE.Stop();

				if (LVDAOMO.IsRun) LVDAOMO.Stop();

				if (LVAUTOTASK.IsRun) LVAUTOTASK.Stop();

				if (LVLOIDAI.IsRun) LVLOIDAI.Stop();

				if (LVAUTOVCVK.IsRun)
				{
					LVAUTOVCVK.Stop();
				}

				if (LVAUTOBINHMAN.IsRun) LVAUTOBINHMAN.Stop();

				if (LVAUTOCALLMAN.IsRun) LVAUTOCALLMAN.Stop();


				if (hook.thpause.IsRun)
				{
					hook.thpause.Stop();
				}
            } 
			catch (Exception ex) 
			{
            }
            //hook.UnHook();
		}
		public void startAllThread()
		{
			if (chkAutoSellFood.Checked && !LVSELL.IsRun)
			{
				/*LVSELL.GetParameter(
					int.Parse(txtCOUNTLUA.Text),
					int.Parse(txtPRICELUA.Text),
					int.Parse(txtSAFELUA.Text),
					int.Parse(txtCOUNTGO.Text),
					int.Parse(txtPRICEGO.Text),
					int.Parse(txtSAFEGO.Text),
					int.Parse(txtCOUNTDA.Text),
					int.Parse(txtPRICEDA.Text),
					int.Parse(txtSAFEDA.Text),
					int.Parse(txtCOUNTSAT.Text),
					int.Parse(txtPRICELSAT.Text),
					int.Parse(txtSAFESAT.Text),
					dtaSELL, int.Parse(txtSELLCHECK.Text) * 60 * 1000);
				*/
				LVSELL.GetParameter(BanTaiNguyen, int.Parse(txtSELLCHECK.Text) * 60 * 1000);
				pnSELL.Enabled = false;
				LVSELL.Auto();
			}

			if (chkAutoBuyResource.Checked && !LVBUYRES.IsRun)
			{
				//LVBUYRES.GetParameter(
				//	int.Parse(txtSAFEGOLD.Text),
				//	dtaBUYRESOURCE, int.Parse(txtBUYRESOURCECHECK.Text) * 60 * 1000);

				LVBUYRES.GetParameter(MuaTaiNguyen);
				
				pnLVBUYRES.Enabled = false;
				LVBUYRES.Auto();
			}
			if (chkAutoST.Checked && !LVTHAOPHAT.IsRun)
			{
				int g1 = 0, g2 = 0, g3 = 0, g4 = 0, g5 = 0;
				try
				{
					g1 = ((Command.CityObj.MilitaryGeneral)cboGeneral.CheckedItems[0]).GeneralId;
					g2 = ((Command.CityObj.MilitaryGeneral)cboGeneral.CheckedItems[1]).GeneralId;
					g3 = ((Command.CityObj.MilitaryGeneral)cboGeneral.CheckedItems[2]).GeneralId;
					g4 = ((Command.CityObj.MilitaryGeneral)cboGeneral.CheckedItems[3]).GeneralId;
					g5 = ((Command.CityObj.MilitaryGeneral)cboGeneral.CheckedItems[4]).GeneralId;
				}
				catch (Exception ex)
				{
				}
				try
				{
					int skmin = txtThaoPhatSyKhi.Text.Trim().Length != 0 ? int.Parse(txtThaoPhatSyKhi.Text.Trim()) : 50;
					bool tubienche = chkThaoPhatBienCheThemQuan.Checked;

					LVTHAOPHAT.GetParameter(TuongDiThaoPhatList, int.Parse(txtTPCHECK.Text) * 60 * 1000);
					pnTHAOPHAT.Enabled = false;
					LVTHAOPHAT.Auto();
				}
				catch (Exception ex)
				{
					lblTHAOPHATMESSAGE.Text = "Chưa chọn đúng tham số";
					chkAutoST.Checked = false;
				}
			}
			if (chkAutoBuild.Checked && !LVBUILD.IsRun)
			{
				LVBUILD.GetParameter( int.Parse(txtBUILDCHECK.Text) * 60 * 1000);
				tvBUILD.Enabled = false;
				cmdReloadBuilding.Enabled = false;
				LVBUILD.Auto();
			}
			if (chkAutoDel.Checked && !LVDEL.IsRun)
			{
				LVDEL.GetParameter(tvDEL, int.Parse(txtDELCHECK.Text) * 60 * 1000);
				tvDEL.Enabled = false;
				LVDEL.Auto();
			}
			if (chkAutoUpDanSo.Checked && !LVANUI.IsRun)
			{
				//LVANUI.GetParameter(AnuiForAuto, int.Parse(txtCHECKANUI.Text) * 60 * 1000);
				LVANUI.GetParameter(AnuiForAuto, chkANUI_TuMuaLua.Checked, long.Parse(txtANUI_VangAnToan.Text), int.Parse(txtCHECKANUI.Text) * 60 * 1000);

				chklstAnUi.Enabled = false;
				LVANUI.Auto();

				//LVANUI.run();
			}
			if (chkAutoVanchuyen.Checked && !LVVANCHUYEN.IsRun)
			{
				LVVANCHUYEN.GetParameter(pnVanchuyen, int.Parse(txtCHECKVANCHUYEN.Text) * 60 * 1000);
				pnVanchuyen.Enabled = false;
				LVVANCHUYEN.Auto();
			}
			if (chkAutoMove.Checked && !LVMOVEDOANHTRAI.IsRun)
			{
				//LVMOVEDOANHTRAI.GetParameter(pnDoanhTrai, int.Parse(txtCHECKMOVE.Text) * 60 * 1000);
				LVMOVEDOANHTRAI.GetParameter(DiChuyenTrai, int.Parse(txtCHECKMOVE.Text) * 60 * 1000);
				pnDoanhTrai.Enabled = false;
				LVMOVEDOANHTRAI.Auto();
			}

			if (chkAutoUpSiKhi.Checked && !LVSIKHI.IsRun)
			{
				LVSIKHI.GetParameter(tvSIKHI, int.Parse(txtOneSiKhi.Text), int.Parse(txtCHECKSIKHI.Text) * 60 * 1000);
				tvSIKHI.Enabled = false;
				LVSIKHI.Auto();
			}

			if (chkAutobuyWepon.Checked && !LVBUYWEPON.IsRun)
			{
				LVBUYWEPON.GetParameter(int.Parse(txtCOUNTWEPON.Text), pnWepon, int.Parse(txtCHECKSIKHI.Text) * 60 * 1000);
				pnWepon.Enabled = false;
				LVBUYWEPON.Auto();
			}


			if (chkAutoBienche.Checked && !LVBIENCHE.IsRun)
			{
				if (LVBIENCHE == null)
					LVBIENCHE = new LVClient.LVThread.BIENCHE(lblBIENCHEMESSAGE);

				LVBIENCHE.GetParameter(10, int.Parse(txtTabBienCheTimeCheck.Text) * 60 * 1000);
				cboBienCheCity.Enabled = false;
				chklstGeneral.Enabled = false;
				btBiencheAccept.Enabled = false;


				//LVBUILD.run();
				LVBIENCHE.Auto();
			}

			if (chkAUTOVCVK.Checked && !LVAUTOVCVK.IsRun)
			{
				LVAUTOVCVK.GetParameter(VanChuyenVuKhi, int.Parse(txtCHECKVANCHUYENVUKHI.Text) * 60 * 1000);
				pnVanChuyenVK.Enabled = false;
				LVAUTOVCVK.Auto();
			}

			if (!LVAUTOTASK.IsRun) LVAUTOTASK.Auto();
			if (!LVCITYTASK.IsRun) LVCITYTASK.Auto();


		}

		private void checkBox1_CheckedChanged_1(object sender, EventArgs e)
		{
			_chuongbao = chkChuong.Checked;
		}

		private void tabLogin_Click(object sender, EventArgs e)
		{

		}

		private void cboXayDungCity_SelectedIndexChanged(object sender, EventArgs e)
		{

			//tv.Nodes.Clear();
			
			LVClient.Common.common.LoadBuildingToTreeViewForbuild_(tvBUILD, cboXayDungCity.SelectedIndex);
			//cboGeneral.Items.AddRange(Command.CityObj.City.AllCity[cboCity.SelectedIndex].AllGeneral);
			
			/*
			TreeNode root = tvBUILD.Nodes[0];

			root.ExpandAll();
			for (int i = 0; i < root.Nodes.Count; i++)
			{
				root.Nodes[i].Checked = Command.CityObj.City.AllCity[cboXayDungCity.SelectedIndex].AllBuilding[i].isUp;
			}
			 */
			cmdReloadBuilding.Visible = true;
			cmdReloadBuilding.Enabled = true;

		}

		private void tvBUILD_Leave(object sender, EventArgs e)
		{
			
		}

		private void tvDEL_Leave(object sender, EventArgs e)
		{
			try
			{
				int cityPost = cboTabHaNhaCity.SelectedIndex;

				//Xay dung mang de xay nha
				TreeNode root = tvDEL.Nodes[0];

				//if (root.Checked) IsBuildAll = true;
				TreeNode tt;
				for (int i = 0; i < root.Nodes.Count; i++)
				{
					Command.CityObj.City.AllCity[cityPost].AllBuilding[i].isDown = root.Nodes[i].Checked;
				}
				int ii;
			}
			catch (Exception ex)
			{
			}
		}

		private void cboTabHaNhaCity_SelectedIndexChanged(object sender, EventArgs e)
		{
            try
            {
                LVClient.Common.common.LoadBuildingToTreeViewForbuild_(tvDEL, cboTabHaNhaCity.SelectedIndex);

                TreeNode root = tvDEL.Nodes[0];

                root.ExpandAll();
                //if (root.Checked) IsBuildAll = true;
                for (int i = 0; i < root.Nodes.Count; i++)
                {
                    root.Nodes[i].Checked = Command.CityObj.City.AllCity[cboTabHaNhaCity.SelectedIndex].AllBuilding[i].isDown;
                }
            }
            catch (Exception ex)
            {

            }

		}

		private void label61_Click(object sender, EventArgs e)
		{

		}

		private void txtDELCHECK_TextChanged(object sender, EventArgs e)
		{

		}

		private void cboGeneral_Leave(object sender, EventArgs e)
		{
			/*
			int cityPost = cboCity.SelectedIndex;
			int task = cboNhiemVu.SelectedIndex;

			//Xay dung mang de xay nha
			TreeNode root = tvDEL.Nodes[0];

			//if (root.Checked) IsBuildAll = true;
			TreeNode tt;
			for (int i = 0; i < root.Nodes.Count; i++)
			{
				Command.CityObj.City.AllCity[cityPost].AllBuilding[i].isDown = root.Nodes[i].Checked;
			}
			 */ 
		}

		private void txtCHECKWEPON_TextChanged(object sender, EventArgs e)
		{

		}

		private void cboNhiemVu_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		private void tabMainTab_Selecting(object sender, TabControlCancelEventArgs e)
		{
			if (!e.TabPage.Enabled)
			{
				e.Cancel = true;
			}
		}

		private void tabMainTab_DrawItem(object sender, DrawItemEventArgs e)
		{
			TabPage page = tabMainTab.TabPages[e.Index];

			if (!page.Enabled)
			{
				using (SolidBrush brush = new SolidBrush(SystemColors.GrayText))
				{
					e.Graphics.DrawString(page.Text, page.Font, brush, e.Bounds);
				}
			}
			else
			{
				using (SolidBrush brush = new SolidBrush(page.ForeColor))
				{
					e.Graphics.DrawString(page.Text, page.Font, brush, e.Bounds);
				}
			}
		}

		private void grbXacNhanHinhAnh_Enter(object sender, EventArgs e)
		{

		}

		private void chkChuong_CheckedChanged(object sender, EventArgs e)
		{
			_chuongbao = chkChuong.Checked;
		}

		private void radHinhAnhKhongLamGi_CheckedChanged(object sender, EventArgs e)
		{
			if (radHinhAnhKhongLamGi.Checked) _tuxacnhananh = 0;
		}

		private void radXacNhanAnhHienAnh_CheckedChanged(object sender, EventArgs e)
		{
			if (radXacNhanAnhHienAnh.Checked) _tuxacnhananh = 1;

		}

		private void radXacNhanAnhTuNhan_CheckedChanged(object sender, EventArgs e)
		{
			if (radXacNhanAnhTuNhan.Checked)
			{
				_tuxacnhananh = 2;
			}
			SoLanTuCheckAnhSaiLienTiep = 0;
			txtXacNhanAnhMaxCheck.Enabled = radXacNhanAnhTuNhan.Checked;
			txtXacNhanAnhMinTimeCheck.Enabled = radXacNhanAnhTuNhan.Checked;
		}

		private void cboLuyenSKCity_SelectedIndexChanged(object sender, EventArgs e)
		{


			/*
			 * 
			  cboGeneral.Items.Clear();
            try {
				showLoadingLabel();
				LVClient.Command.Common.GetGeneral(cboCity.SelectedIndex, false); 
				cboGeneral.Items.AddRange(Command.CityObj.City.AllCity[cboCity.SelectedIndex].AllGeneral);


				hideLoadingLabel();
            } catch (Exception ex) { }
			 * 
			 * 
			*/
		}

		private void btLuyenSykhiNapLai_Click(object sender, EventArgs e)
		{
			try
			{
				this.Enabled = false;
				LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfoIntoCity();
				Common.common.LoadGeneralForUpSiKhi(tvSIKHI, false);
				this.Enabled = true;
			}
			catch (Exception ex)
			{
				this.Enabled = true;
			}
		}

		
		private void cboBienCheCity_SelectedIndexChanged(object sender, EventArgs e)
		{
			chklstGeneral.Items.Clear();
            try {
				showLoadingLabel();
				LVClient.Command.Common.GetGeneral(cboBienCheCity.SelectedIndex, false);
				chklstGeneral.Items.AddRange(Command.CityObj.City.AllCity[cboBienCheCity.SelectedIndex].MilitaryGeneral);

				
				hideLoadingLabel();
            } catch (Exception ex) { }
        }

		private void btBiencheAccept_Click(object sender, EventArgs e)
		{
			try
			{
				Command.CityObj.MilitaryGeneral onegenral;
				LVClient.Common.BienChe bienche;
				//int cityid = cboBienCheCity.SelectedIndex;
				int citypost = cboBienCheCity.SelectedIndex;
				int cityid = Command.CityObj.City.AllCity[citypost].id;

				for (int i = 0; i < chklstGeneral.CheckedItems.Count; i++)
				{
					bienche = new LVClient.Common.BienChe();
					onegenral = (Command.CityObj.MilitaryGeneral)chklstGeneral.CheckedItems[i];
					bienche.cityid = cityid;

					bienche.generalid = onegenral.GeneralId;
					bienche.generalname = onegenral.GeneralName;
					bienche.cityname = Command.CityObj.City.AllCity[citypost].name;
					bienche.bobinhamount = txtBiencheBoBinh.Text.Trim().Length != 0 ? int.Parse(txtBiencheBoBinh.Text) : 0;
					bienche.kybinhamount = txtBiencheKybinh.Text.Trim() != "" ? int.Parse(txtBiencheKybinh.Text) : 0;
					bienche.cungthuamount = txtBienCheCungThu.Text.Trim().Length != 0 ? int.Parse(txtBienCheCungThu.Text) : 0;
					bienche.xemount = txtBiencheXe.Text.Trim().Length != 0 ? int.Parse(txtBiencheXe.Text) : 0;
					bienche.nangsykhi = chkBienCheTuNangSK.Checked;
					if (bienche.bobinhamount != 0 || bienche.kybinhamount != 0 || bienche.cungthuamount != 0 || bienche.xemount != 0)
						ListBienChe.Add(bienche);
				}
				
					LVClient.Common.common.LoadGeneralForBienChe(tvBienCheList);
			}
			catch (Exception ex)
			{
				MessageBox.Show("Sai cái gì đó, xem lại đê!");
			}

		}

		private void btBienCheBo_Click(object sender, EventArgs e)
		{

			int index;
			for (int i = 0; i < tvBienCheList.Nodes.Count; i++)
			{
				if (tvBienCheList.Nodes[i].Checked)
				{
					index = tvBienCheList.Nodes[i].Index;
					ListBienChe.RemoveAt(index);
					tvBienCheList.Nodes.RemoveAt(index);
					
				}	
			}
			LVClient.Common.common.LoadGeneralForBienChe(tvBienCheList);

/*
			if (tvBienCheList.SelectedNode != null)
			{

				tvBienCheList.Nodes.Remove(tvBienCheList.SelectedNode);
				LVClient.Common.common.LoadGeneralForBienChe(tvBienCheList);
			}
*/
		}

		private void chkAutoBienche_CheckedChanged(object sender, EventArgs e)
		{
			if (chkAutoBienche.Checked)
			{
				if (LVBIENCHE== null)
					LVBIENCHE = new LVClient.LVThread.BIENCHE(lblBIENCHEMESSAGE);

				LVBIENCHE.GetParameter(10, int.Parse(txtTabBienCheTimeCheck.Text) * 60 * 1000);
				cboBienCheCity.Enabled = false;
				chklstGeneral.Enabled = false;
				btBiencheAccept.Enabled = false;

				
				//LVBUILD.run();
				LVBIENCHE.Auto();
			}
			else
			{
				LVBIENCHE.Stop();
				cboBienCheCity.Enabled = true;
				chklstGeneral.Enabled = true;
				btBiencheAccept.Enabled = true;

			}
		}

		private void chkAutoDieuPhai_CheckedChanged(object sender, EventArgs e)
		{
			
			
			if (chkAutoDieuPhai.Checked)
			{
				bool found1 = false;
				bool found2 = false;
				LVClient.Command.CommonObj.DieuPhaiTuong g;
				btTapDieuPhaiBo.Enabled = false;

				for (int i = 0; i < DieuPhaiQuanVanVo.Count; i++)
				{
					g = ((LVClient.Command.CommonObj.DieuPhaiTuong) DieuPhaiQuanVanVo[i]);
					if (g.tasktype == LVClient.Command.CommonObj.DieuPhaiTuong.TASKTYPE.DaoMo)
					{
						if (!found1)
						{
							LVDAOMO.GetParameter(g.cityID, g.X, g.Y, g.timetoruninmilisecond);
							grbtabDieuPhaiDaoMo.Enabled = false;
							grbTabDieuPhaiLoiDai.Enabled = false;
							LVDAOMO.Auto();
							found1 = true;
						}
						if (found1 & found2) break;
						
					}

					if (g.tasktype == LVClient.Command.CommonObj.DieuPhaiTuong.TASKTYPE.LoiDai)
					{
						if (!found2)
						{
							LVLOIDAI.GetParameter(DieuPhaiQuanVanVo, g.timetoruninmilisecond);
							grbtabDieuPhaiDaoMo.Enabled = false;
							grbTabDieuPhaiLoiDai.Enabled = false;
							LVLOIDAI.Auto();
							found2 = true;
						}
						if (found1 & found2) break;
					}


				}
				if (!found1 & !found2)
				{
					chkAutoDieuPhai.Checked = false;
					btTapDieuPhaiBo.Enabled = true;
					grbtabDieuPhaiDaoMo.Enabled = true;
					grbTabDieuPhaiLoiDai.Enabled = true;

					lblDIEUPHAIMESSAGE.Text = "Không chọn thằng quan nào để phái cả, check lại đê";
						
				}
			}
			else
			{
				LVDAOMO.Stop();
				LVLOIDAI.Stop();
				grbtabDieuPhaiDaoMo.Enabled = true;
				grbTabDieuPhaiLoiDai.Enabled = true;
				btTapDieuPhaiBo.Enabled = true;
			
			}
		}

		private void btTest_Click(object sender, EventArgs e)
		{
            int i;
           
           
            
            DeleteNhacNhoAdmin();

			LVClient.Control.War w = new LVClient.Control.War();
			w.Show();

			return;

			int generalid;
			int cityid;
			int sk;


			
			generalid = 412227;
			// -16702 "5.3"
			cityid = -16702;


			//cityid = 13139; //iwunu5
			//generalid = 426324;			//,"Lão Nạp Thạch

			LVClient.Command.CityObj.MilitaryGeneral[] g = Command.Common.GetGeneralInforInLuyenBinh(cityid);

			//sk = LVClient.Command.Common.GetGeneralSyKhiInLuyenBinh(cityid, generalid);

			cityid = 13139;	// iwunu5
			generalid = 4426324;  //Lam nap thach

			 g = Command.Common.GetGeneralInforInLuyenBinh(cityid);

			//sk = LVClient.Command.Common.GetGeneralSyKhiInLuyenBinh(cityid, generalid);
			return;






			// test di loi dai

			 cityid = 13139;	// iwunu5

			int genid = 426324;  //Lam nap thach
			string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
			string para;
			LVClient.Command.City.SwitchCitySlow(cityid);
			para = "lCityTentID=" + cityid + "&lGeneralID=" + genid + "&lLevel=1";
			Hashtable r= Command.OPT.Execute(21, para, false);
			if (r != null && r["DATA"].ToString() == "{\"ret\":0}")
			{
				bool ok = true;

			}

			//Command.Common.GetGeneral(0, true);
			//Command.Common.GetGeneralMilitary(10718,405711);
			//Common.BienCheQuan.BienChe(10718, 405711, 100, 100, 100);
			//Common.BienCheQuan.BienChe(ListBienChe );
			int g1 = 277645, g2 = 275162, g3 = 313841, g4 = 0, g5 = 0, idnhiemvu = 4;
		
			Command.Common.GetMaxNhiemVu();
			Command.OPT.DanhSonTac(idnhiemvu, g1, g2, g3, g4, g5, cookies);

			i = 0;
			
			Hashtable ret;
			//405723,"Quân Lạc Xuyên"
			 generalid = 405723;
			//[10718,"iwunu7(Đô thành)
			 cityid = 10718;




			// tu ddi dao mo
			int X = 299;
			int Y = -111;
			cityid = 13139;
			int mapid;
			//http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=72&0.24057125736018958&DestX=299&DestY=-111
			para = "DestX=" + X + "&DestY=" + Y;
			ret = LVClient.Command.Common.Execute(72, para, true);

			if (ret == null) 
				return;
			mapid = int.Parse(ret["map_id"].ToString());

			return;


			

			
			sk = LVClient.Command.Common.GetGeneralSyKhiInLuyenBinh(cityid, generalid);


			//412227,"Tề Hậu"
			generalid = 412227;
			// -16702 "5.3"
			cityid = -16702;

			sk = LVClient.Command.Common.GetGeneralSyKhiInLuyenBinh(cityid, generalid);

			return;

			
			
			// tu ddi dao mo
			 X = 299;
			Y = -111;
			 cityid = 13139;
						//http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=72&0.24057125736018958&DestX=299&DestY=-111
			para = "DestX=" + X + "&DestY=" + Y;
			ret = LVClient.Command.Common.Execute(72, para, true);

			if (ret == null) return;
			mapid = int.Parse(ret["map_id"].ToString());

			//get danh sach quan van
			//http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=15&0.31696323126782144&lType=1&tid=13139

			 cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

			para = "lType=1&tid=" + cityid;
			ret = LVClient.Command.Common.Execute(15, para, true, cookies);

			ArrayList gen = (ArrayList) ret["generals"];  // 3=0, 5=0, 13=0
			 genid = int.Parse(((ArrayList)gen[0])[0].ToString());

			// cu quan van di
			//http://s3.linhvuong.zooz.vn/GateWay/OPT.ashx?id=100&0.4721581634738514&DestMapID=1004086&HeroID=412545&tid=11697
			para = "DestMapID=" + mapid + "&HeroID=" + genid + "&tid=" + cityid;
			ret = LVClient.Command.OPT.Execute(100, para, true, cookies);
			int iii;
		}

		private void chklstGeneral_SelectedIndexChanged(object sender, EventArgs e)
		{
			bool haschecked;
			if (chklstGeneral.CheckedItems.Count > 0)
				btBiencheAccept.Enabled = true;
			else
				btBiencheAccept.Enabled = false;
		}

		private void txtBiencheBoBinh_Leave(object sender, EventArgs e)
		{
			if (txtBiencheBoBinh.Text.Trim().Length == 0) txtBiencheBoBinh.Text = "0";
		}

		private void txtBiencheKybinh_Leave(object sender, EventArgs e)
		{
			if (txtBiencheKybinh.Text.Trim().Length == 0) txtBiencheKybinh.Text = "0";
		}

		private void txtBienCheCungThu_Leave(object sender, EventArgs e)
		{
			if (txtBienCheCungThu.Text.Trim().Length == 0) txtBienCheCungThu.Text = "0";
		}

		private void txtBiencheXe_Leave(object sender, EventArgs e)
		{
			if (txtBiencheXe.Text.Trim().Length == 0) txtBiencheXe.Text = "0";
		}

		private void tabBienChe_Click(object sender, EventArgs e)
		{

		}

		private void textBox2_TextChanged(object sender, EventArgs e)
		{

		}

		private void groupBox5_Enter(object sender, EventArgs e)
		{

		}


		public  void PhaiQuanVan(LVClient.Common.PhaiQuanVanDaoMo pqv)
		{
			if (pqv.check)
			{
				LVDAOMO.Auto();
			}
		}
/*		private void gbTuPhaiQuanVan_Leave(object sender, EventArgs e)
		{
			try
			{
				QuanVanDaoMo.check = chkTienIchTuphaiQuanVan.Checked;
				if (QuanVanDaoMo.check)
				{
					QuanVanDaoMo.cityid = Command.CityObj.City.AllCity[cboTuphaiquanvanCity.SelectedIndex].id;
					QuanVanDaoMo.X = int.Parse(txtTuphaiQuanVanX.Text);
					QuanVanDaoMo.Y = int.Parse(txtTuphaiQuanVanY.Text);
					QuanVanDaoMo.Time = 60000;
					//PhaiQuanVan(QuanVanDaoMo);
				}
				else
				{
					//LVTIENICH.Stop();
				}

			}
			catch (Exception ex)
			{
			}
		}
*/
		private void pnTHAOPHAT_Leave(object sender, EventArgs e)
		{
			

		}

		

		private void chklstAnUi_Leave(object sender, EventArgs e)
		{
			AnuiForAuto = new ArrayList();

			for (int i = 0; i < chklstAnUi.CheckedItems.Count; i++)
			{
				AnuiForAuto.Add(((LVClient.Command.CityObj.City)chklstAnUi.CheckedItems[i]).id);
			}
		}

		private void pnUPGRADE_Leave(object sender, EventArgs e)
		{
			UpgradeForAuto = new ArrayList();
			if (cboCityForUpgrade.SelectedItem != null)
			{
				UpgradeForAuto.Add(((LVClient.Command.CityObj.City)cboCityForUpgrade.SelectedItem).id);
				TreeNode root = tvUpdate.Nodes["root"];
				foreach (TreeNode t in root.Nodes)
				{
					foreach (TreeNode c in t.Nodes)
					{
						if (c.Checked)
						{
							UpgradeForAuto.Add( c.Name);

						}
					}
				}
			}
		}

		private void toolStripMenuItem1_Click(object sender, EventArgs e)
		{
			this.BringToFront();
			this.Show();
			this.WindowState = FormWindowState.Normal;
		}

		private void toolStripMenuItem2_Click(object sender, EventArgs e)
		{
			this.Close(); ;
		}

		private void cboCityForUpgrade_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		private void cboTuphaiquanvanCity_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		private void btTabDieuPhaiPhaiQuanVan_Click(object sender, EventArgs e)
		{
			try
			{		
				/*
				QuanVanDaoMo.cityid = Command.CityObj.City.AllCity[cboTabDieuPhaiThanhPhaiQuanVan.SelectedIndex].id;
				QuanVanDaoMo.X = int.Parse(txtTabDieuPhaiDaoMoX.Text);
				QuanVanDaoMo.Y = int.Parse(txtTabDieuPhaiDaoMoY.Text);
				QuanVanDaoMo.Time = 60000;
				QuanVanDaoMo.check = true;
				*/
				Command.CommonObj.DieuPhaiTuong dieuphai = new LVClient.Command.CommonObj.DieuPhaiTuong();
				dieuphai.cityID = Command.CityObj.City.AllCity[cboTabDieuPhaiThanhPhaiQuanVan.SelectedIndex].id;
				dieuphai.X = int.Parse(txtTabDieuPhaiDaoMoX.Text);
				dieuphai.Y = int.Parse(txtTabDieuPhaiDaoMoY.Text);
				dieuphai.generaltype = Command.CommonObj.DieuPhaiTuong.GENERALTYPE.QuanVan;
				dieuphai.timetoruninmilisecond = 60000; ;
				dieuphai.desc = "Điều phái quan văn từ thành " + Command.CityObj.City.AllCity[cboTabDieuPhaiThanhPhaiQuanVan.SelectedIndex].name
									+ " đến mỏ có tọa độ (" + dieuphai.X + "," + dieuphai.Y + ")";
				dieuphai.tasktype = Command.CommonObj.DieuPhaiTuong.TASKTYPE.DaoMo;
				DieuPhaiQuanVanVo.Add(dieuphai);
				
				cboTabDieuPhaiThanhPhaiQuanVan.SelectedIndex = -1;
				txtTabDieuPhaiDaoMoX.Text = "";
				txtTabDieuPhaiDaoMoY.Text= "";
				btTabDieuPhaiPhaiQuanVan.Enabled = false;
				showDataForGridDieuPhai();
			}
			catch (Exception ex)
			{
				MessageBox.Show("Chọn chưa đúng các tham số", "Lỗi rồi", MessageBoxButtons.OK, MessageBoxIcon.Error);
			}
		}

		public void showDataForGridDieuPhai()
		{
			Command.CommonObj.DieuPhaiTuong dieuphai;
			lstboxTabDieuPhaiDieuPhai.DataSource = null;
			lstboxTabDieuPhaiDieuPhai.Items.Clear();

			lstboxTabDieuPhaiDieuPhai.DataSource = DieuPhaiQuanVanVo;
			lstboxTabDieuPhaiDieuPhai.DisplayMember = "GetDesc";
			lstboxTabDieuPhaiDieuPhai.ValueMember = "GetID";


		}

		private void btTapDieuPhaiBo_Click(object sender, EventArgs e)
		{
			long id ;
			for (int i = 0; i < lstboxTabDieuPhaiDieuPhai.SelectedItems.Count; i++)
			{
				DieuPhaiQuanVanVo.Remove((Command.CommonObj.DieuPhaiTuong)lstboxTabDieuPhaiDieuPhai.SelectedItems[i]);
			}
			showDataForGridDieuPhai();
		}

		private void cboTabDieuPhaiThanhPhaiQuanVan_SelectedIndexChanged(object sender, EventArgs e)
		{
			int tmp;
			if (txtTabDieuPhaiDaoMoX.Text.Trim() != ""  && txtTabDieuPhaiDaoMoY.Text.Trim() != ""  &
					cboTabDieuPhaiThanhPhaiQuanVan.SelectedItem != null && int.TryParse(txtTabDieuPhaiDaoMoX.Text, out tmp)
						&& int.TryParse(txtTabDieuPhaiDaoMoY.Text, out tmp))
				btTabDieuPhaiPhaiQuanVan.Enabled = true;
			else
				btTabDieuPhaiPhaiQuanVan.Enabled = false;
		}

		private void txtTabDieuPhaiDaoMoX_TextChanged(object sender, EventArgs e)
		{
			int tmp;
			if (txtTabDieuPhaiDaoMoX.Text.Trim() != "" && txtTabDieuPhaiDaoMoY.Text.Trim() != "" &
					cboTabDieuPhaiThanhPhaiQuanVan.SelectedItem != null && int.TryParse(txtTabDieuPhaiDaoMoX.Text, out tmp)
						&& int.TryParse(txtTabDieuPhaiDaoMoY.Text, out tmp))
				btTabDieuPhaiPhaiQuanVan.Enabled = true;
			else
				btTabDieuPhaiPhaiQuanVan.Enabled = false;
		}

		private void txtTabDieuPhaiDaoMoY_TextChanged(object sender, EventArgs e)
		{
			int tmp;
			if (txtTabDieuPhaiDaoMoX.Text.Trim() != "" && txtTabDieuPhaiDaoMoY.Text.Trim() != "" &
					cboTabDieuPhaiThanhPhaiQuanVan.SelectedItem != null && int.TryParse(txtTabDieuPhaiDaoMoX.Text, out tmp)
						&& int.TryParse(txtTabDieuPhaiDaoMoY.Text, out tmp))
				btTabDieuPhaiPhaiQuanVan.Enabled = true;
			else
				btTabDieuPhaiPhaiQuanVan.Enabled = false;
		}

		private void cbTabDieuPhaiThanhPhaiDiLoiDai_SelectedIndexChanged(object sender, EventArgs e)
		{
			int cityid;
			int count = 0;
			if (cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedItem == null)
			{
				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
				return;
			}
			cbTabDieuPhaiQuanVanVoDiLoiDai.Items.Clear();
			cityid = Command.CityObj.City.AllCity[cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedIndex].id;

			ArrayList argen = Command.Common.GetAllGeneralVanVo(cityid);

			if (argen == null || argen.Count == 0)
			{
				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
				return;
			}

			
			cbTabDieuPhaiQuanVanVoDiLoiDai.Items.AddRange(argen.ToArray());

			if (cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedItem == null
					|| cbTabDieuPhaiQuanVanVoDiLoiDai.SelectedItem == null
					|| cboCapLoiDai.SelectedItem == null)
			
				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
			else
				btTabDieuPhai_PhaiDiLoiDai.Enabled = true;


		}

		private void cbTabDieuPhaiQuanVanVoDiLoiDai_SelectedIndexChanged(object sender, EventArgs e)
		{
			if (cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedItem == null
					|| cbTabDieuPhaiQuanVanVoDiLoiDai.SelectedItem == null
					|| cboCapLoiDai.SelectedItem == null)

				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
			else
				btTabDieuPhai_PhaiDiLoiDai.Enabled = true;

		}

		private void cboCapLoiDai_SelectedIndexChanged(object sender, EventArgs e)
		{
			if (cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedItem == null
					|| cbTabDieuPhaiQuanVanVoDiLoiDai.SelectedItem == null
					|| cboCapLoiDai.SelectedItem == null)

				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
			else
				btTabDieuPhai_PhaiDiLoiDai.Enabled = true;

		}

		private void btTabDieuPhai_PhaiDiLoiDai_Click(object sender, EventArgs e)
		{

			if (cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedItem == null
					|| cbTabDieuPhaiQuanVanVoDiLoiDai.SelectedItem == null
					|| cboCapLoiDai.SelectedItem == null)

				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
			else
				btTabDieuPhai_PhaiDiLoiDai.Enabled = true;


			try
			{
				Command.CommonObj.DieuPhaiTuong dieuphai = new LVClient.Command.CommonObj.DieuPhaiTuong();
				Command.CityObj.MilitaryGeneral g = (Command.CityObj.MilitaryGeneral) cbTabDieuPhaiQuanVanVoDiLoiDai.SelectedItem;
				if (g == null)
				{
					btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
					return;
				}

				dieuphai.cityID = Command.CityObj.City.AllCity[cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedIndex].id;
				dieuphai.generalid = g.GeneralId;
				dieuphai.generalname = g.GeneralName;
				dieuphai.generaltype = g.Generaltype;
				string str = cboCapLoiDai.SelectedItem.ToString();
				dieuphai.loidailevel = int.Parse( str.Substring(0, str.IndexOf(".")));
				dieuphai.timetoruninmilisecond = 60000; ;

				if (dieuphai.generaltype == Command.CommonObj.DieuPhaiTuong.GENERALTYPE.QuanVan)
				{
					dieuphai.desc = "Điều phái quan văn " + dieuphai.generalname + " từ thành " + Command.CityObj.City.AllCity[cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedIndex].name
										+ " đi lôi đài cấp " + dieuphai.loidailevel;
				}
				else
				{
					dieuphai.desc = "Điều phái quan võ " + dieuphai.generalname + " từ thành " + Command.CityObj.City.AllCity[cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedIndex].name
										+ " đi lôi đài cấp " + dieuphai.loidailevel;

				}
					
				dieuphai.tasktype = Command.CommonObj.DieuPhaiTuong.TASKTYPE.LoiDai;
				
				DieuPhaiQuanVanVo.Add(dieuphai);

				//cbTabDieuPhaiThanhPhaiDiLoiDai.SelectedIndex = -1;
				cbTabDieuPhaiQuanVanVoDiLoiDai.SelectedIndex = -1;
				cboCapLoiDai.SelectedIndex					  = -1;
				btTabDieuPhai_PhaiDiLoiDai.Enabled = false;
				showDataForGridDieuPhai();
			}
			catch (Exception ex)
			{
				MessageBox.Show("Chọn chưa đúng các tham số", "Lỗi rồi", MessageBoxButtons.OK, MessageBoxIcon.Error);
			}
		}

		
		private void tabBanTaiNguyen_Leave(object sender, EventArgs e)
		{
			
		}

		private void chkBanTN_LUA_TB_CheckedChanged(object sender, EventArgs e)
		{
			
		}

		private void chkBanTN_GO_TB_CheckedChanged(object sender, EventArgs e)
		{
			
		}

		private void chkBanTN_SAT_TB_CheckedChanged(object sender, EventArgs e)
		{
			
		}

		private void chkBanTN_DA_TB_CheckedChanged(object sender, EventArgs e)
		{
			
		}

		private void pnSELL_Paint(object sender, PaintEventArgs e)
		{

		}

		private void btSelectAllLua_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaSELL.Rows.Count; i++)
			{
				dtaSELL.Rows[i].Cells[2].Value = bantaiNguyenLuaCheckAll;
			}
			bantaiNguyenLuaCheckAll = !bantaiNguyenLuaCheckAll;
		}

		private void btSelectAllGo_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaSELL.Rows.Count; i++)
			{
				dtaSELL.Rows[i].Cells[3].Value = bantaiNguyenGoCheckAll;				
			}
			bantaiNguyenGoCheckAll = !bantaiNguyenGoCheckAll;
		}

		private void btSelectAllSat_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaSELL.Rows.Count; i++)
			{
				dtaSELL.Rows[i].Cells[4].Value = bantaiNguyenSatCheckAll;
			}
			bantaiNguyenSatCheckAll = !bantaiNguyenSatCheckAll;
		}

		private void btSelectAllDa_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaSELL.Rows.Count; i++)
			{
				dtaSELL.Rows[i].Cells[5].Value = bantaiNguyenDaCheckAll;
			}
			bantaiNguyenDaCheckAll = !bantaiNguyenDaCheckAll;
		}

		private void btMuaTNSelectAllLua_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaBUYRESOURCE.Rows.Count; i++)
			{
				dtaBUYRESOURCE.Rows[i].Cells[2].Value = muataiNguyenLuaCheckAll;
			}
			muataiNguyenLuaCheckAll = !muataiNguyenLuaCheckAll;
		}

		private void btMuaTNSelectAllGo_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaBUYRESOURCE.Rows.Count; i++)
			{
				dtaBUYRESOURCE.Rows[i].Cells[3].Value = muataiNguyenGoCheckAll;
			}
			muataiNguyenGoCheckAll = !muataiNguyenGoCheckAll;
		}

		private void btMuaTNSelectAllSat_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaBUYRESOURCE.Rows.Count; i++)
			{
				dtaBUYRESOURCE.Rows[i].Cells[4].Value = muataiNguyenSatCheckAll;
			}
			muataiNguyenSatCheckAll = !muataiNguyenSatCheckAll;
		}

		private void btMuaTNSelectAllDa_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < dtaBUYRESOURCE.Rows.Count; i++)
			{
				dtaBUYRESOURCE.Rows[i].Cells[5].Value = muataiNguyenDaCheckAll;
			}
			muataiNguyenDaCheckAll = !muataiNguyenDaCheckAll;
		}

		private void tabMainTab_Leave(object sender, EventArgs e)
		{

		}

		private void tabMuaTaiNguyen_Leave(object sender, EventArgs e)
		{
			try
			{

				MuaTaiNguyen.VangAnToan = long.Parse(txtSAFEGOLD.Text);
				MuaTaiNguyen.TimeToRunInMinute = double.Parse(txtBUYRESOURCECHECK.Text);
				MuaTaiNguyen.MuaTheoDonViKho = (rdMuaTNMuaTheoDonVi.Checked);
				MuaTaiNguyen.GiaTri = double.Parse(txtMuaTNGioiHanMua.Text);

				DataTable temp = (DataTable)dtaBUYRESOURCE.DataSource;

				LVClient.Command.CommonObj.MuaTaiNguyenObj.cityInfo_ ctinfo;

				ArrayList arCity = new ArrayList();
				if (temp != null)
				{
					for (int i = 0; i < temp.Rows.Count; i++)
					{
						ctinfo = new LVClient.Command.CommonObj.MuaTaiNguyenObj.cityInfo_();
						ctinfo.CityId = int.Parse((temp.Rows[i]["ID_TT"]).ToString());
						ctinfo.CityName = (temp.Rows[i]["NAME_TT"]).ToString();

						ctinfo.MuaLua = (bool)temp.Rows[i]["BUY_LUA"];
						ctinfo.MuaGo = (bool)temp.Rows[i]["BUY_GO"];
						ctinfo.MuaSat = (bool)temp.Rows[i]["BUY_SAT"];
						ctinfo.MuaDa = (bool)temp.Rows[i]["BUY_DA"];

						if (ctinfo.MuaLua || ctinfo.MuaGo || ctinfo.MuaDa || ctinfo.MuaSat)
							arCity.Add(ctinfo);
					}

					if (arCity.Count > 0)
					{
						MuaTaiNguyen.newCityInfo(arCity.Count);
						for (int i = 0; i < arCity.Count; i++)
							MuaTaiNguyen.CityInfo[i] = (LVClient.Command.CommonObj.MuaTaiNguyenObj.cityInfo_)arCity[i];
						
					}
				}
				
			}
			catch (Exception ex)
			{
				MessageBox.Show("Có lỗi sai gì đó ở mua tài nguyên, kiểm tra lại đê", "Lỗi rồi", MessageBoxButtons.OK, MessageBoxIcon.Question);

			}
		}

		private void rdMuaTNMuaTheoPhanTram_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdMuaTNMuaTheoDonVi_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void pnDoanhTrai_Leave(object sender, EventArgs e)
		{
			Command.CommonObj.DoiTraiObj objDoiTrai = null ;
			DiChuyenTrai = new ArrayList();
			LVClient.Command.CommonObj.doitrai vc;
			bool found = false;
 
			foreach (object obj in pnDoanhTrai.Controls)
			{
				found = false;
				vc = (LVClient.Command.CommonObj.doitrai)obj;
				if (vc.chkOK.Checked)
				{
					try
					{
						objDoiTrai = new LVClient.Command.CommonObj.DoiTraiObj();				
						objDoiTrai.TraiID = vc.id;
						objDoiTrai.TraiName = vc.txtTen.Text;
						objDoiTrai.targetX = int.Parse(vc.X.Text);
						objDoiTrai.targetY = int.Parse(vc.Y.Text);
						found = true;
						if (vc.X.Text.Trim() == "" || vc.Y.Text.Trim() == "") found = false;
					}
					catch (Exception ex)
					{
						vc.chkOK.Checked = false;
					}

					if (found) DiChuyenTrai.Add(objDoiTrai);
				}
			}
			

		}

	

		private void pnSELL_Leave(object sender, EventArgs e)
		{
			try
			{
				BanTaiNguyen.SalesOff = chkBanTN_SalesOff.Checked;


				BanTaiNguyen.LUA.BanCoDinh = rdBTNLuaAnToanCoDinh.Checked;
				BanTaiNguyen.LUA.SoLuongBan = int.Parse(txtCOUNTLUA.Text);
				BanTaiNguyen.LUA.SoLuongAnToan = int.Parse(txtSAFELUA.Text);
				
				if (rdBanTN_LUA_CODINH.Checked) BanTaiNguyen.LUA.LoaiBan = 1; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_LUA_TRUNGBINH.Checked) BanTaiNguyen.LUA.LoaiBan = 2; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_LUA_THAPNHAT.Checked) BanTaiNguyen.LUA.LoaiBan = 3; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				BanTaiNguyen.LUA.CongThucNhan = rdBanTN_LUA_TB_Nhan.Checked;
				BanTaiNguyen.LUA.GiaTri = double.Parse(txtBanTN_LUA_TB_Heso.Text);

				BanTaiNguyen.GO.BanCoDinh = rdBTNGoAnToanCoDinh.Checked;
				BanTaiNguyen.GO.SoLuongBan = int.Parse(txtCOUNTGO.Text);
				BanTaiNguyen.GO.SoLuongAnToan = int.Parse(txtSAFEGO.Text);
				if (rdBanTN_GO_CODINH.Checked) BanTaiNguyen.GO.LoaiBan = 1; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_GO_TRUNGBINH.Checked) BanTaiNguyen.GO.LoaiBan = 2; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_GO_THAPNHAT.Checked) BanTaiNguyen.GO.LoaiBan = 3; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				BanTaiNguyen.GO.CongThucNhan = rdBanTN_GO_TB_Nhan.Checked;
				BanTaiNguyen.GO.GiaTri = double.Parse(txtBanTN_GO_TB_Heso.Text);

				BanTaiNguyen.SAT.BanCoDinh = rdBTNSatAnToanCoDinh.Checked;
				BanTaiNguyen.SAT.SoLuongBan = int.Parse(txtCOUNTSAT.Text);
				BanTaiNguyen.SAT.SoLuongAnToan = int.Parse(txtSAFESAT.Text);
				if (rdBanTN_SAT_CODINH.Checked) BanTaiNguyen.SAT.LoaiBan = 1; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_SAT_TRUNGBINH.Checked) BanTaiNguyen.SAT.LoaiBan = 2; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_SAT_THAPNHAT.Checked) BanTaiNguyen.SAT.LoaiBan = 3; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				BanTaiNguyen.SAT.CongThucNhan = rdBanTN_SAT_TB_Nhan.Checked;
				BanTaiNguyen.SAT.GiaTri = double.Parse(txtBanTN_SAT_TB_Heso.Text);

				BanTaiNguyen.DA.BanCoDinh = rdBTNDaAnToanCoDinh.Checked;
				BanTaiNguyen.DA.SoLuongBan = int.Parse(txtCOUNTDA.Text);
				BanTaiNguyen.DA.SoLuongAnToan = int.Parse(txtSAFEDA.Text);
				if (rdBanTN_DA_CODINH.Checked) BanTaiNguyen.DA.LoaiBan = 1; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_DA_TRUNGBINH.Checked) BanTaiNguyen.DA.LoaiBan = 2; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				if (rdBanTN_DA_THAPNHAT.Checked) BanTaiNguyen.DA.LoaiBan = 3; // BanTaiNguyen.LOAIBAN.THEOGIACODINH;
				BanTaiNguyen.DA.CongThucNhan = rdBanTN_DA_TB_Nhan.Checked;
				BanTaiNguyen.DA.GiaTri = double.Parse(txtBanTN_DA_TB_Heso.Text);


				DataTable temp = (DataTable)dtaSELL.DataSource;

				LVClient.Command.CommonObj.BanTaiNguyenObj.cityInfo_ ctinfo;

				ArrayList arCity = new ArrayList();

				for (int i = 0; i < temp.Rows.Count; i++)
				{
					ctinfo = new LVClient.Command.CommonObj.BanTaiNguyenObj.cityInfo_();
					ctinfo.CityId = int.Parse((temp.Rows[i]["ID_TT"]).ToString());
					ctinfo.CityName = (temp.Rows[i]["NAME_TT"]).ToString();

					ctinfo.BanLua = (bool)temp.Rows[i]["SELL_LUA"];
					ctinfo.BanGo = (bool)temp.Rows[i]["SELL_GO"];
					ctinfo.BanDa = (bool)temp.Rows[i]["SELL_DA"];
					ctinfo.BanSat = (bool)temp.Rows[i]["SELL_SAT"];

					if (ctinfo.BanLua || ctinfo.BanGo || ctinfo.BanDa || ctinfo.BanSat)
						arCity.Add(ctinfo);
					//BanTaiNguyen.CityInfo[i] = ctinfo;
				}

				if (arCity.Count > 0)
				{
					BanTaiNguyen.NewCityInfo(arCity.Count);
					for (int i = 0; i < arCity.Count; i++)
						BanTaiNguyen.CityInfo[i] = (LVClient.Command.CommonObj.BanTaiNguyenObj.cityInfo_)arCity[i];

					//BanTaiNguyen.CityInfo = (LVClient.Command.CommonObj.BanTaiNguyenObj.cityInfo_[]) arCity.ToArray();
				}
			}
			catch (Exception ex)
			{
				MessageBox.Show("Có lỗi sai gì đó ở bán tài nguyên, kiểm tra lại đê", "Lỗi rồi", MessageBoxButtons.OK, MessageBoxIcon.Question);
				
			}
		}

		private void txtBanTN_DA_TB_Heso_TextChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_DA_TB_Nhan_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_DA_TB_Cong_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_SAT_TB_Nhan_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_SAT_TB_Cong_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_GO_TB_Nhan_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_GO_TB_Cong_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_LUA_TB_Nhan_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_LUA_TB_Cong_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void txtBanTN_LUA_TB_Heso_TextChanged(object sender, EventArgs e)
		{

		}

		private void txtBanTN_GO_TB_Heso_TextChanged(object sender, EventArgs e)
		{

		}

		private void txtBanTN_SAT_TB_Heso_TextChanged(object sender, EventArgs e)
		{

		}

		private void rdBanTN_GO_CODINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_GO_CODINH.Checked)
			{
				rdBanTN_GO_TB_Cong.Enabled = false;
				rdBanTN_GO_TB_Nhan.Enabled = false;
			}
			else
			{
				rdBanTN_GO_TB_Cong.Enabled = true;
				rdBanTN_GO_TB_Nhan.Enabled = true;
			}
		}

		private void rdBanTN_LUA_CODINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_LUA_CODINH.Checked)
			{
				rdBanTN_LUA_TB_Cong.Enabled = false;
				rdBanTN_LUA_TB_Nhan.Enabled = false;
			}
			else
			{
				rdBanTN_LUA_TB_Cong.Enabled = true;
				rdBanTN_LUA_TB_Nhan.Enabled = true;
			}
		}

		private void rdBanTN_LUA_TRUNGBINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_LUA_TRUNGBINH.Checked)
			{
				rdBanTN_LUA_TB_Cong.Enabled = true;
				rdBanTN_LUA_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_LUA_TB_Cong.Enabled = false;
				rdBanTN_LUA_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_LUA_THAPNHAT_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_LUA_THAPNHAT.Checked)
			{
				rdBanTN_LUA_TB_Cong.Enabled = true;
				rdBanTN_LUA_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_LUA_TB_Cong.Enabled = false;
				rdBanTN_LUA_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_GO_TRUNGBINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_GO_TRUNGBINH.Checked)
			{
				rdBanTN_GO_TB_Cong.Enabled = true;
				rdBanTN_GO_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_GO_TB_Cong.Enabled = false;
				rdBanTN_GO_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_GO_THAPNHAT_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_GO_THAPNHAT.Checked)
			{
				rdBanTN_GO_TB_Cong.Enabled = true;
				rdBanTN_GO_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_GO_TB_Cong.Enabled = false;
				rdBanTN_GO_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_SAT_CODINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_SAT_CODINH.Checked)
			{
				rdBanTN_SAT_TB_Cong.Enabled = false;
				rdBanTN_SAT_TB_Nhan.Enabled = false;
			}
			else
			{
				rdBanTN_SAT_TB_Cong.Enabled = true;
				rdBanTN_SAT_TB_Nhan.Enabled = true;
			}
		}

		private void rdBanTN_SAT_TRUNGBINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_SAT_TRUNGBINH.Checked)
			{
				rdBanTN_SAT_TB_Cong.Enabled = true;
				rdBanTN_SAT_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_SAT_TB_Cong.Enabled = false;
				rdBanTN_SAT_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_SAT_THAPNHAT_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_SAT_THAPNHAT.Checked)
			{
				rdBanTN_SAT_TB_Cong.Enabled = true;
				rdBanTN_SAT_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_SAT_TB_Cong.Enabled = false;
				rdBanTN_SAT_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_DA_CODINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_DA_CODINH.Checked)
			{
				rdBanTN_DA_TB_Cong.Enabled = false;
				rdBanTN_DA_TB_Nhan.Enabled = false;
			}
			else
			{
				rdBanTN_DA_TB_Cong.Enabled = true;
				rdBanTN_DA_TB_Nhan.Enabled = true;
			}
		}

		private void rdBanTN_DA_TRUNGBINH_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_DA_TRUNGBINH.Checked)
			{
				rdBanTN_DA_TB_Cong.Enabled = true;
				rdBanTN_DA_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_DA_TB_Cong.Enabled = false;
				rdBanTN_DA_TB_Nhan.Enabled = false;
			}
		}

		private void rdBanTN_DA_THAPNHAT_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBanTN_DA_THAPNHAT.Checked)
			{
				rdBanTN_DA_TB_Cong.Enabled = true;
				rdBanTN_DA_TB_Nhan.Enabled = true;
			}
			else
			{
				rdBanTN_DA_TB_Cong.Enabled = false;
				rdBanTN_DA_TB_Nhan.Enabled = false;
			}
		}

		

		private void chkHaNhaDelAll_CheckedChanged(object sender, EventArgs e)
		{
			Command.CityObj.City.isDowndAll = chkHaNhaDelAll.Checked;
			cboTabHaNhaCity.Enabled = !chkHaNhaDelAll.Checked;
			tvDEL.Enabled = !chkHaNhaDelAll.Checked;			
		}

		private void pnXayNha_Paint(object sender, PaintEventArgs e)
		{

		}

		private void chkXayNhaAll_CheckedChanged(object sender, EventArgs e)
		{
			cboXayDungCity.Enabled = !chkXayNhaAll.Checked;
			tvBUILD.Enabled = !chkXayNhaAll.Checked;
			cmdReloadBuilding.Enabled = !chkXayNhaAll.Checked;

			Command.CityObj.City.isBuildAll = chkXayNhaAll.Checked;	
		}

		private void chkXayNha_TuMuaTaiNguyen_CheckedChanged(object sender, EventArgs e)
		{
			txtXayNha_VangAnToan.Enabled = chkXayNha_TuMuaTaiNguyen.Checked;
		}

		private void pnXayNha_Leave(object sender, EventArgs e)
		{
			try
			{

				Command.CityObj.City.isBuyRes = chkXayNha_TuMuaTaiNguyen.Checked;
				if (chkXayNha_TuMuaTaiNguyen.Checked) Command.CityObj.City.goldSafe = long.Parse(txtXayNha_VangAnToan.Text);

				if (chkXayNhaAll.Checked) return;

				int cityPost = cboXayDungCity.SelectedIndex;
				if (cityPost < 0) return;

				try
				{
					//Xay dung mang de xay nha
					TreeNode root = tvBUILD.Nodes[0];

					//if (root.Checked) IsBuildAll = true;
					TreeNode tt;
					for (int i = 0; i < root.Nodes.Count; i++)
					{
						Command.CityObj.City.AllCity[cityPost].AllBuilding[i].isUp = root.Nodes[i].Checked;
					}
				}
				catch (Exception ex)
				{
				}
			}
			catch (Exception ex)
			{
				MessageBox.Show("Có lỗi gì đó trong phần Xây dựng");
			}
		}

		private void label21_Click(object sender, EventArgs e)
		{

		}

		private void chkANUI_TuMuaLua_CheckedChanged(object sender, EventArgs e)
		{
			txtANUI_VangAnToan.Enabled = chkANUI_TuMuaLua.Checked;
		}

		private void tvBUILD_Leave_1(object sender, EventArgs e)
		{
			try
			{

				Command.CityObj.City.isBuyRes = chkXayNha_TuMuaTaiNguyen.Checked;
				if (chkXayNha_TuMuaTaiNguyen.Checked) Command.CityObj.City.goldSafe = long.Parse(txtXayNha_VangAnToan.Text);

				if (chkXayNhaAll.Checked) return;

				int cityPost = cboXayDungCity.SelectedIndex;
				if (cityPost < 0) return;
				try
				{
					//Xay dung mang de xay nha
					TreeNode root = tvBUILD.Nodes[0];

					//if (root.Checked) IsBuildAll = true;
					TreeNode tt;
					for (int i = 0; i < root.Nodes.Count; i++)
					{
						Command.CityObj.City.AllCity[cityPost].AllBuilding[i].isUp = root.Nodes[i].Checked;
					}
				}
				catch (Exception ex)
				{
				}
			}
			catch (Exception ex)
			{
				MessageBox.Show("Có lỗi gì đó trong phần Xây dựng");
			}
		}

		private void btThaoPhatReload_Click(object sender, EventArgs e)
		{
			btThaoPhatReload.Enabled = false;
			if (cboCity.SelectedIndex < 0)
			{
				MessageBox.Show("Chưa chọn thành");
				return;

			}
			cboGeneral.Items.Clear();
			try
			{
				showLoadingLabel();

				Command.CityObj.City city = (Command.CityObj.City ) cboCity.SelectedItem;
				LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfoIntoCity();

				//LVClient.Command.Common.GetGeneral(cboCity.SelectedIndex, true);

				if (Command.CityObj.City.AllCity[cboCity.SelectedIndex].MilitaryGeneral == null)
				{
					MessageBox.Show("Lỗi rồi, có thể mạng lởm, đợi tý làm lại đê");
					return;

				}

				cboGeneral.Items.Clear();
				cboGeneral.Items.AddRange(Command.CityObj.City.AllCity[cboCity.SelectedIndex].MilitaryGeneral);
				
				int g;
				for (int i = 0; i < cboGeneral.Items.Count; i++)
				{
					g = ((Command.CityObj.MilitaryGeneral)cboGeneral.Items[i]).GeneralId;

					g = ((Command.CityObj.MilitaryGeneral)cboGeneral.Items[i]).GeneralId;
					for (int k = 0; k < TuongDiThaoPhatList.Count; k++)
					{
						if (g == ((Common.GeneralThaoPhat)TuongDiThaoPhatList[k]).GeneralId)
							cboGeneral.SetItemChecked(i, true);
					}
				}	 				
			}
			catch (Exception ex) { }

			finally
			{
				hideLoadingLabel();
				btThaoPhatReload.Enabled = true;
			}
		}

		private void btTienIchRuongGetData_Click(object sender, EventArgs e)
		{
			try
			{
				int count = 0;
				btTienIchRuongGetData.Enabled = false;

				do
				{
					QuocKho_Ruong = Command.Common.GetGem(0);
					count++;
				} while (QuocKho_Ruong == null && count < 10);

				if (QuocKho_Ruong == null)
				{
					MessageBox.Show(" Lỗi rồi, thử làm lại xem sao nha");
					return;
				}


				
				cbTienIchChonRuong.Items.Clear();
				cbTienIchMoRuongRuongChonThanh.Items.Clear();
				//Common.Ruong ruong = new LVClient.Common.Ruong();

				int[] arGemID = new int[QuocKho_Ruong.Count];
			

				QuocKho_Ruong.Keys.CopyTo(arGemID, 0);
				Array.Sort(arGemID);

				for (int i = 0; i < arGemID.Length; i++)
				{
					cbTienIchChonRuong.Items.Add(arGemID[i] + ". " + Common.Ruong.GetRuongName(arGemID[i]));
				}

				
				cbTienIchChonRuong.Enabled = true;
				cbTienIchMoRuongRuongChonThanh.Enabled = true;
				txtTienIchRuongSoluong.Enabled = true;
				LVClient.Command.CityObj.City city;
				for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
				{
					city = LVClient.Command.CityObj.City.AllCity[i];
					if (city.id > 0)
					{

						cbTienIchMoRuongRuongChonThanh.Items.Add(city);
					}
				}
				EnableMoRuong();

			}
			catch (Exception ex)
			{
				cbTienIchChonRuong.Enabled = false;			  
				cbTienIchMoRuongRuongChonThanh.Enabled = false;
				txtTienIchRuongSoluong.Enabled = false;
			}

			finally
			{
				btTienIchRuongGetData.Enabled = true;
			}
		}

		/*private void btTienIchRuongGetData_Click(object sender, EventArgs e)
		{
			try
			{
				btTienIchRuongGetData.Enabled = false;

				//http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=2&0.6633130316506091&nid=0

				Hashtable result = Command.Common.Execute(2, "nid=0", false);

				//string str = "{Table:[{gem_id:1,counts:259},{gem_id:2,counts:265},{gem_id:3,counts:84},{gem_id:6,counts:93},{gem_id:7,counts:6},{gem_id:8,counts:10},{gem_id:11,counts:8},{gem_id:12,counts:15},{gem_id:13,counts:3},{gem_id:16,counts:261},{gem_id:17,counts:196},{gem_id:21,counts:54},{gem_id:24,counts:141},{gem_id:25,counts:162},{gem_id:35,counts:6},{gem_id:50,counts:2}],ret:0,nid:0}";

				if (result == null)
				{
					MessageBox.Show(" Lỗi rồi, thử làm lại xem sao nha");
					return;
				}


				string str = result["DATA"].ToString().Trim();
				if (!str.Contains("ret:0"))
				{
					MessageBox.Show(" Lỗi rồi, thử làm lại xem sao nha");
					return;
				}


				string s1 = str.Substring(str.IndexOf("[") + 1);
				s1 = s1.Substring(0, s1.IndexOf("]"));
				string[] ar = s1.Split(new char[] { ',' }, StringSplitOptions.None);

				QuocKho_Ruong.Clear();
				cbTienIchChonRuong.Items.Clear();
				cbTienIchMoRuongRuongChonThanh.Items.Clear();
				int i = 0;
				int key;
				string value;
				Common.Ruong ruong = new LVClient.Common.Ruong();
				while (i < ar.Length)
				{
					key = int.Parse(ar[i].Substring(ar[i].IndexOf(":") + 1).Trim());
					i++;
					value = ar[i].Substring(ar[i].IndexOf(":") + 1).Trim();
					value = value.Substring(0, value.Length - 1);
					i++;
					QuocKho_Ruong.Add(key, value);
					cbTienIchChonRuong.Items.Add(key + ". " + ruong.GetRuongName(key));
				}

				cbTienIchChonRuong.Enabled = true;
				cbTienIchMoRuongRuongChonThanh.Enabled = true;
				txtTienIchRuongSoluong.Enabled = true;
				LVClient.Command.CityObj.City city;
				for (i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
				{
					city = LVClient.Command.CityObj.City.AllCity[i];
					if (city.id > 0)
					{

						cbTienIchMoRuongRuongChonThanh.Items.Add(city);
					}
				}


			}
			catch (Exception ex)
			{
				cbTienIchChonRuong.Enabled = false;
				cbTienIchMoRuongRuongChonThanh.Enabled = false;
				txtTienIchRuongSoluong.Enabled = false;
			}

			finally
			{
				btTienIchRuongGetData.Enabled = true;
			}
		}
		*/


		private void cbTienIchChonRuong_SelectedIndexChanged(object sender, EventArgs e)
		{
			try
			{
				string value = cbTienIchChonRuong.SelectedItem.ToString();
				if (value == "") return;
				value = value.Substring(0, value.IndexOf("."));
				string amount = QuocKho_Ruong[int.Parse(value)].ToString();
				lblTienIchSoLuongCo.Text = amount;
				EnableMoRuong();

			}
			catch (Exception ex)
			{
				MessageBox.Show("Lỗi gì đó rồi :( ");
			}
		}

		private void EnableMoRuong()
		{
			if (cbTienIchChonRuong.SelectedItem != null && cbTienIchMoRuongRuongChonThanh.SelectedItem != null)
			{
				string sl = txtTienIchRuongSoluong.Text;
				int vl;
				if (int.TryParse(sl, out vl))
				{
					if (vl > 0)
						btTienIchRuongOpen.Enabled = true;
					else
						btTienIchRuongOpen.Enabled = false;
				}

			}
			else
			{
				btTienIchRuongOpen.Enabled = false;
			}
			
		}

		private void cbTienIchMoRuongRuongChonThanh_SelectedIndexChanged(object sender, EventArgs e)
		{
			EnableMoRuong();
		}

		private void txtTienIchRuongSoluong_TextChanged(object sender, EventArgs e)
		{
			EnableMoRuong();
		}

		private void btTienIchRuongOpen_Click(object sender, EventArgs e)
		{
			try
			{
				if (cbTienIchChonRuong.SelectedItem == null || cbTienIchMoRuongRuongChonThanh == null)
				{
					MessageBox.Show("Chưa chọn đúng tham số");
					EnableMoRuong();
					return;
				}

				lblTienIchMoRuong_waitmsg.Enabled = true;
				lblTienIchMoRuong_waitmsg.Visible = true;
				grbTienIchMoRuong_group.Enabled = false;

				string str = cbTienIchChonRuong.SelectedItem.ToString();
				int ruongid = int.Parse(str.Substring(0, str.IndexOf(".")));
				LVClient.Command.CityObj.City city = (LVClient.Command.CityObj.City)cbTienIchMoRuongRuongChonThanh.SelectedItem;
				int cityid = city.id;
				int amount = int.Parse(txtTienIchRuongSoluong.Text);

				string cookies = cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
				LVClient.Command.City.SwitchCitySlow(cityid);
				// mo ruong
				string para = "lBoxID=" + ruongid;
				//string para = "lBoxID=" + ruongid + "&lcid=" + cityid + "&lCityCampID=" + cityid + "&cityid=" + cityid;
				// para += "&lcityid=" +  cityid  + "&tid=" +  cityid + "&ttid=" +  cityid;
				// para += "&lcid=" + cityid + "&cid=" + cityid; ;

				int success = 0;
				Hashtable result;
				int havenow = int.Parse(lblTienIchSoLuongCo.Text);
				for (int i = 0; i < amount; i++)
				{
					result = Command.Common.Execute(48, para, true, cookies);
					if (result != null && result["ret"].ToString() == "0")
					{
						success++;
						havenow--;
						lblTienIchSoLuongCo.Text = havenow.ToString() ;
						Application.DoEvents();
					}
				}
				/*
				if (success > 0)
				{
					int remain = int.Parse(lblTienIchSoLuongCo.Text) - success;
					lblTienIchSoLuongCo.Text = remain.ToString();
				}
				 * */
			}
			catch (Exception ex)
			{
				MessageBox.Show("Hic, có lỗi gì rùi, không thực hiện được");

			}

			finally
			{
				lblTienIchMoRuong_waitmsg.Enabled = false;
				lblTienIchMoRuong_waitmsg.Visible = false;

				grbTienIchMoRuong_group.Enabled = true; ;

			}
		}

		

		private void btVCVKOK_Click(object sender, EventArgs e)
		{
			try
			{
				


				btVCVKOK.Enabled = false;
				int sourceCityID;		// = ((Command.CityObj.City)cbVCVKThanhDi.SelectedItem).id;
				int destCityID;		
				int loaivkid;	// = ((Common.Wepons)cbVCVKLoaiVK.SelectedItem).id;
				int tongsoluong = int.Parse(txtVCVKTongSoLuong.Text);
				int soluong = int.Parse(txtVCVKSoLuong.Text);

				Command.CityObj.City destCity;
				for (int i = 0; i < chklVCVKThanhDi.CheckedItems.Count; i++)
				{
					sourceCityID = ((Command.CityObj.City)chklVCVKThanhDi.CheckedItems[i]).id;
					for (int j = 0; j < chklVCVKThanhDen.CheckedItems.Count; j++)
					{
						destCityID = ((Command.CityObj.City)chklVCVKThanhDen.CheckedItems[j]).id;
						for (int k = 0; k < chklVCVKLoaiVuKhi.CheckedItems.Count; k++)
						{
							loaivkid = ((Common.Wepons)chklVCVKLoaiVuKhi.CheckedItems[k]).id;
							VanChuyenVuKhi.Add(new Command.CommonObj.VanChuyenVK(sourceCityID, destCityID, loaivkid, tongsoluong,soluong));
						}

					}
					//destCity = (Command.CityObj.City)chklVCVKThanhDen.CheckedItems[i];
					//VanChuyenVuKhi.Add(new Command.CommonObj.VanChuyenVK(sourceCityID, destCity.id, loaivkid, soluong));
				}

				for (int i = 0; i < chklVCVKThanhDi.Items.Count; i++)
					chklVCVKThanhDi.SetItemChecked(i, false);

				for (int i = 0; i < chklVCVKThanhDen.Items.Count; i++)
					chklVCVKThanhDen.SetItemChecked(i, false);

				for (int i = 0; i < chklVCVKLoaiVuKhi.Items.Count; i++)
					chklVCVKLoaiVuKhi.SetItemChecked(i, false);

	
				chklVCVKThanhDen.ClearSelected();
				chklVCVKLoaiVuKhi.ClearSelected();

				chklVCVKThanhDi.EndUpdate();

				Common.common.LoadDataResultForVCVK(lstVCVKResult);

			}
			catch (Exception ex)
			{
				MessageBox.Show("Sai/thiếu tham số gì đó");
			}
			finally
			{
				btVCVKOK.Enabled = true;
			}
		}

		private void btVCVKCancel_Click(object sender, EventArgs e)
		{
			Command.CommonObj.VanChuyenVK vcvk;
			for (int i = 0; i < lstVCVKResult.SelectedItems.Count; i++)
			{
				vcvk = ((Command.CommonObj.VanChuyenVK)lstVCVKResult.SelectedItems[i]);
				VanChuyenVuKhi.Remove(vcvk);
			}
			Common.common.LoadDataResultForVCVK(lstVCVKResult);

		}

		private void label106_Click(object sender, EventArgs e)
		{

		}

		private void chkAUTOVCVK_CheckedChanged(object sender, EventArgs e)
		{
			try
			{

				if (chkAUTOVCVK.Checked)
				{
					if (VanChuyenVuKhi.Count > 0)
					{
						LVAUTOVCVK.GetParameter(VanChuyenVuKhi, int.Parse(txtCHECKVANCHUYENVUKHI.Text) * 60 * 1000);
						pnVanChuyenVK.Enabled = false;
						LVAUTOVCVK.Auto();
					}
					else
					{
						lblAUTOVCVKMESSAGE.Text = "Chưa chọn đúng tham số";
						chkAUTOVCVK.Checked = false;
					}
				}
				else
				{
					LVAUTOVCVK.Stop();
					pnVanChuyenVK.Enabled = true;
				}
			}
			catch (Exception ex)
			{
				lblAUTOVCVKMESSAGE.Text = "Chưa chọn đúng tham số";
				chkAUTOVCVK.Checked = false;
			}
		}
		//}


		public void DeleteNhacNhoAdmin()
		{
			try
			{
				int count = 0;
				int page = 1;
				while (count < 5)
				{
					count++;

					while (true && page < 100)
					{
						Application.DoEvents();

						Hashtable result;

						//string header = "GET http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/message HTTP/1.1\n";

						string header = "GET http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/Interfaces/message_list.aspx?n=n&page=" + page + " HTTP/1.1\n";

						header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
						header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
						header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
						header += "Accept-Language: en-us,en;q=0.5\n";
						header += "Accept-Encoding: gzip,deflate\n";
						header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
						header += "Keep-Alive: 300\n";
						header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/city\n";
						header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
						header += "Content-Type: application/x-www-form-urlencoded\n";
						header += "\n";
						result = LVClient.Web.LVWeb.SendAndReceive(header, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, true);
						if (result == null)
						{
							page = 1;
							break;
						}
						string data = result["DATA"].ToString();
						if (data.Contains("Object moved"))		// het trang
						{
							page = 1;
							break;
						}
						ParseHTML parse = new ParseHTML();
						parse.Source = data;

						//parse.Source = "<tr class=\"tr yellow6\" id=\"tr_4506176\" onmouseover=\"onmover('4506176');\" onmouseout=\"onmout('4506176');\"><td width=\"28\" height=\"26px\"><input type=\"checkbox\" name=\"IsChek\" onclick=\"check_click('4506176');\" id=\"check_4506176\" value=\"4506176\" /></td><td><a href=\"javascript:void(0)\" onclick=\"get_message('4506176',1,0);\" class=\"but_12\">Nh?c nh?</a><label id=\"lb_4506176\">(Chua d?c)</label><input id=\"noread_4506176\" value=\"1\" type=\"hidden\" /></td><td><a onclick=\"Dipan.SanGuo.Common.CloseDialog('_float');Dipan.SanGuo.Common.GetUserInfo(0); return false;\" href=\"#\" class=\"but_12\">Admin</a></td><td class=\"yellow1\">2009-08-28 07:12:20</td></tr>";
						//	 <tr class="tr yellow6" id="tr_4506176" onmouseover="onmover('4506176');" onmouseout="onmout('4506176');"><td width="28" height="26px"><input type="checkbox" name="IsChek" onclick="check_click('4506176');" id="check_4506176" value="4506176" /></td><td><a href="javascript:void(0)" onclick="get_message('4506176',1,0);" class="but_12">Nh?c nh?</a><label id="lb_4506176">(Chua d?c)</label><input id="noread_4506176" value="1" type="hidden" /></td><td><a onclick="Dipan.SanGuo.Common.CloseDialog('_float');Dipan.SanGuo.Common.GetUserInfo(0); return false;" href="#" class="but_12">Admin</a></td><td class="yellow1">2009-08-28 07:12:20</td></tr>

						string checkID = "";
						ArrayList removeID = new ArrayList();
						while (!parse.Eof())
						{
							char ch = parse.Parse();
							if (ch == 0)
							{

								AttributeList tag = parse.GetTag();
								if (tag.Name.ToLower() == "a")
								{
									if (parse.InnerHTML == "Nhắc nhở")
									{
										LVClient.HTMLParse.Attribute arr = (LVClient.HTMLParse.Attribute)tag.List[1];
										checkID = arr.Value;
										checkID = checkID.Substring(checkID.IndexOf("(") + 2);
										checkID = checkID.Substring(0, checkID.IndexOf("'"));
									}
									if (parse.InnerHTML == "Admin")
									{
										removeID.Add(checkID);
									}
								}
							}
						}

						if (removeID.Count <= 0)
						{
							page++;
							continue;
						}
						string str = "<?xml version='1.0' encoding='utf-8'?>";
						str += "<root><delete><seqnos>";

						for (int i = 0; i < removeID.Count; i++)
						{
							str += removeID[i].ToString() + ",";
						}
						str = str.Substring(0, str.Length - 1);

						str += "</seqnos><del_type>1</del_type><noread_num>1</noread_num></delete></root>";

						header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/Interfaces/read_message.aspx HTTP/1.1\n";

						header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
						header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
						header += "Accept: */*";
						header += "method: POST /Interfaces/read_message.aspx HTTP/1.1\n";
						header += "x-requested-with: XMLHttpRequest\n";
						header += "Accept-Language: en-us,en;q=0.5\n";
						header += "Accept-Encoding: gzip, deflatelin\n";
						header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
						header += "Keep-Alive: 300\n";
						header += "Pragma: no-cache\n";
						header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/message\n";
						header += "Content-Type: application/x-www-form-urlencoded\n";
						header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
						header += "Content-Length: " + (str.Length) + "\n";
						header += "\n";

						Hashtable res = LVClient.Web.LVWeb.SendAndReceive(header + str, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, true);
						page++;
					} // end while true
				} // end while (count < 10)
			} //end try
			catch (Exception ex)
			{
			}

		}

		private void timerForAuto_Tick(object sender, EventArgs e)
		{
			try
			{
				if (LVAUTOVCVK.IsRun && VanChuyenVuKhi.Count > 0)
				{
					Common.common.LoadDataResultForVCVK(lstVCVKResult);
				}
			}
			catch (Exception ex)
			{

			}
		}

		private void chkAutoLinhBongLoc_CheckedChanged(object sender, EventArgs e)
		{
			TuLinhBongLoc = chkAutoLinhBongLoc.Checked;
		}

		private void cboThaoPhatSLTuongDanh1Dich_SelectedIndexChanged(object sender, EventArgs e)
		{
			/*
			int sotuongdanh1dich= cboThaoPhatSLTuongDanh1Dich.SelectedIndex;
			if (sotuongdanh1dich > 0)
			{
				cboThaoPhatPhuongThucTanCong.Enabled = true;
			}
			else
			{
				cboThaoPhatPhuongThucTanCong.Enabled = false;
			}
			 */ 
		}

		private void label87_Click(object sender, EventArgs e)
		{

		}

	

		private void rdBTNLuaAnToanCoDinh_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBTNLuaAnToanCoDinh.Checked)
			{
				lblBTNLuaDVSoluong.Text = "tấn";
				lblBTNLuaDVAnToan.Text = "tấn";
				txtCOUNTLUA.Text = BanTNSoLuongBanCoDinhDefault.ToString(); ;
				txtSAFELUA.Text = BanTNAnToanCoDinhDefault.ToString();
			}
			else
			{
				lblBTNLuaDVSoluong.Text = "% kho";
				lblBTNLuaDVAnToan.Text = "% kho";
				txtCOUNTLUA.Text = BanTNSoLuongBanPercentDefault.ToString(); ;
				txtSAFELUA.Text = BanTNAnToanPercentDefault.ToString();

			}
		}

		private void rdBTNLuaPercentCoDinh_CheckedChanged(object sender, EventArgs e)
		{
			if (!rdBTNLuaPercentCoDinh.Checked)
			{
				lblBTNLuaDVSoluong.Text = "tấn";
				lblBTNLuaDVAnToan.Text = "tấn";
			}
			else
			{
				lblBTNLuaDVSoluong.Text = "% kho";
				lblBTNLuaDVAnToan.Text = "% kho";

			}
		}

		private void rdBTNGoAnToanCoDinh_CheckedChanged(object sender, EventArgs e)
		{
			if (rdBTNGoAnToanCoDinh.Checked)
			{
				lblBTNGoDVSoluong.Text = "tấn";
				lblBTNGoDVAnToan.Text = "tấn";
				txtCOUNTGO.Text = BanTNSoLuongBanCoDinhDefault.ToString(); ;
				txtSAFEGO.Text = BanTNAnToanCoDinhDefault.ToString();
			}
			else
			{
				lblBTNGoDVSoluong.Text = "% kho";
				lblBTNGoDVAnToan.Text = "% kho";
				txtCOUNTGO.Text = BanTNSoLuongBanPercentDefault.ToString(); ;
				txtSAFEGO.Text = BanTNAnToanPercentDefault.ToString();

			}
		}

		private void rdBTNGoPercentCoDinh_CheckedChanged(object sender, EventArgs e)
		{
			if (!rdBTNGoPercentCoDinh.Checked)
			{
				lblBTNGoDVSoluong.Text = "tấn";
				lblBTNGoDVAnToan.Text = "tấn";
			}
			else
			{
				lblBTNGoDVSoluong.Text = "% kho";
				lblBTNGoDVAnToan.Text = "% kho";

			}
		}

		private void rdBTNSatAnToanCoDinh_CheckedChanged(object sender, EventArgs e)
		{

			if (rdBTNSatAnToanCoDinh.Checked)
			{
				lblBTNSatDVSoluong.Text = "tấn";
				lblBTNSatDVAnToan.Text = "tấn";
				txtCOUNTSAT.Text = BanTNSoLuongBanCoDinhDefault.ToString(); ;
				txtSAFESAT.Text = BanTNAnToanCoDinhDefault.ToString();
			}
			else
			{
				lblBTNSatDVSoluong.Text = "% kho";
				lblBTNSatDVAnToan.Text = "% kho";
				txtCOUNTSAT.Text = BanTNSoLuongBanPercentDefault.ToString(); ;
				txtSAFESAT.Text = BanTNAnToanPercentDefault.ToString();

			}
		}

		private void rdBTNDaAnToanCoDinh_CheckedChanged(object sender, EventArgs e)
		{

			if (rdBTNDaAnToanCoDinh.Checked)
			{
				lblBTNDaDVSoluong.Text = "tấn";
				lblBTNDaDVAnToan.Text = "tấn";
				txtCOUNTDA.Text = BanTNSoLuongBanCoDinhDefault.ToString(); ;
				txtSAFEDA.Text = BanTNAnToanCoDinhDefault.ToString();
			}
			else
			{
				lblBTNDaDVSoluong.Text = "% kho";
				lblBTNDaDVAnToan.Text = "% kho";
				txtCOUNTDA.Text = BanTNSoLuongBanPercentDefault.ToString(); ;
				txtSAFEDA.Text = BanTNAnToanPercentDefault.ToString();

			}
		}

		private void cmdTienIchXoaNhacNhoAdmin_Click(object sender, EventArgs e)
		{
			cmdTienIchXoaNhacNhoAdmin.Enabled = false;
			DeleteNhacNhoAdmin();
			cmdTienIchXoaNhacNhoAdmin.Enabled = true;

		}

		private void chkAutoThongBaoDanhTuongViengTham_CheckedChanged(object sender, EventArgs e)
		{
			ThongBaoDanhTuongViengTham = chkAutoThongBaoDanhTuongViengTham.Checked;
		}

		private void timerForTBDanhTuongViengTham_Tick(object sender, EventArgs e)
		{
			try
			{
				lblLoadingResMessage.Text = "Kiểm tra danh tướng viếng thăm ...";
			}
			catch (Exception ex) { }
			ShowCoDanhTuongViengTham();

			lblLoadingResMessage.Text = "";
		}

		private void ShowCoDanhTuongViengTham()
		{
			if (ThongBaoDanhTuongViengTham)
			{
                string g = "";
                g=Command.Build.GetGeneralViengTham();
				if (g != "")
				{
					string message = "Hi " + LVClient.Web.LVWeb.lvusername + "!!!\r\n" + g;
					string title = "Hi " + LVClient.Web.LVWeb.lvusername + "!!!";
					notifyIcon1.ShowBalloonTip(3000, "", message, ToolTipIcon.None);
				}
			}			

		}

		private void btAutoHienAnhDeCheck_Click(object sender, EventArgs e)
		{
			btAutoHienAnhDeCheck.Enabled = false;
			LVClient.Web.LVWeb.processCheckImage();
			btAutoHienAnhDeCheck.Enabled = true;

		}
		private bool AnuiCheckAll = false;
		private void btAnUiCheckAll_Click(object sender, EventArgs e)
		{
			AnuiCheckAll = !AnuiCheckAll;
			for (int i = 0; i < chklstAnUi.Items.Count; i++)
			{
				chklstAnUi.SetItemChecked(i, AnuiCheckAll);
			}
		}

		private void lblPanelLoading_Click(object sender, EventArgs e)
		{

		}

		private void txtXacNhanAnhMaxCheck_TextChanged(object sender, EventArgs e)
		{

		}

		private void txtXacNhanAnhMaxCheck_Leave(object sender, EventArgs e)
		{
			string str = txtXacNhanAnhMaxCheck.Text;

			int value;
			if (!int.TryParse(str, out value))
			{
				MessageBox.Show("Số lần tự check sai tối đa phải là số nguyên");
				txtXacNhanAnhMaxCheck.Focus();
			}
			if (value <= 0)
			{
				MessageBox.Show("Số lần tự check sai tối đa phải là số nguyên");
				txtXacNhanAnhMaxCheck.Focus();
			}
		}

		private void txtXacNhanAnhMinTimeCheck_TextChanged(object sender, EventArgs e)
		{

		}

		private void txtXacNhanAnhMinTimeCheck_Leave(object sender, EventArgs e)
		{
			string str = txtXacNhanAnhMinTimeCheck.Text;

			int value;
			if (!int.TryParse(str, out value))
			{
				MessageBox.Show("Thời gian check tiếp theo phải là số nguyên");
				txtXacNhanAnhMinTimeCheck.Focus();
			}

			if (value <= 0)
			{
				MessageBox.Show("Thời gian check tiếp theo phải là số nguyên");
				txtXacNhanAnhMinTimeCheck.Focus();
			}
		}

		private void txtThaoPhatTongQuanMin_TextChanged(object sender, EventArgs e)
		{
			
		}

		private void chkAutoBanThuong_CheckedChanged(object sender, EventArgs e)
		{
			TuBanThuongDoDe = chkAutoBanThuong.Checked;
		}

		private void pnTHAOPHAT_Paint(object sender, PaintEventArgs e)
		{

		}

		private void chkAutoAnUiKhiDanNo_CheckedChanged(object sender, EventArgs e)
		{
			TuBanAnUiKhiDanNo = chkAutoAnUiKhiDanNo.Checked;
		}

		private void chkAutoTuXoaNhacNho_CheckedChanged(object sender, EventArgs e)
		{
			TuXoaNhacNhoCuaAdmin =  chkAutoTuXoaNhacNho.Checked;
		}

		private void cbProxyProtocol_SelectedIndexChanged(object sender, EventArgs e)
		{
			string protocol = cbProxyProtocol.SelectedItem.ToString();

			switch (protocol)
			{

				case "NONE":
					txtProxyServer.Enabled = false;
					txtProxyPort.Enabled = false;
					txtProxyUser.Enabled = false;
					txtProxyPassword.Enabled = false;
					break;

				case "HTTP":
					txtProxyServer.Enabled = true;
					txtProxyPort.Enabled = true;
					txtProxyUser.Enabled = false;
					txtProxyPassword.Enabled = false;
					break;
				case "SOCKS4":
					txtProxyServer.Enabled = true;
					txtProxyPort.Enabled = true;
					txtProxyUser.Enabled = true;
					txtProxyPassword.Enabled = false;
					break;

				case "SOCKS4a":
					txtProxyServer.Enabled = true;
					txtProxyPort.Enabled = true;
					txtProxyUser.Enabled = true;
					txtProxyPassword.Enabled = false;
					break;

				case "SOCKS5":
					txtProxyServer.Enabled = true;
					txtProxyPort.Enabled = true;
					txtProxyUser.Enabled = true;
					txtProxyPassword.Enabled = false;
					break;


			}

		}

		private void tabBinhMan_Click(object sender, EventArgs e)
		{

		}

		private void cbTabBinhManThanhXuatQuan_SelectedIndexChanged(object sender, EventArgs e)
		{
			if (cbTabBinhManThanhXuatQuan.SelectedItem == null) return;

			chkTabBinhManTuongXuatTran.Items.Clear();
			LVClient.Command.CityObj.City city = (LVClient.Command.CityObj.City ) cbTabBinhManThanhXuatQuan.SelectedItem ;
			
			
			if (city.MilitaryGeneral == null) city.MilitaryGeneral = LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfo(city.id);

			if (city.MilitaryGeneral == null)
			{
				MessageBox.Show("Lỗi rồi, mạng lởm quá, chờ tý rồi thử lại đê.", "Mạng lởm quá");
				return;
			}

			chkTabBinhManTuongXuatTran.Items.AddRange(city.MilitaryGeneral);
		}

		private void btTabBinhManXacNhan_Click(object sender, EventArgs e)
		{

			try
			{
				int num10;
				int selectedIndex = this.cbTabBinhManThanhXuatQuan.SelectedIndex;
				int id = LVClient.Command.CityObj.City.AllCity[selectedIndex].id;

				string str = this.cbTabBinhManPhuongThucTanCong.SelectedItem.ToString();
				int num3 = int.Parse(str.Substring(0, str.IndexOf(".")));
				string str2 = str.Substring(str.IndexOf(".") + 2);

				str = this.cbTabBinhManPhuongThucChonMucTieu.SelectedItem.ToString();
				int num4 = int.Parse(str.Substring(0, str.IndexOf(".")));
				string str3 = str.Substring(str.IndexOf(".") + 2);

				str = this.cbTabBinhManMuuKeTrongChienTruong.SelectedItem.ToString();
				int muuKeTrongChienTruongID = int.Parse(str.Substring(0, str.IndexOf(".")));
				string muuKeTrongChienTruongName = str.Substring(str.IndexOf(".") + 2);

				bool tuKhoiPhucTrangThai = chkTabBinhManTuKhoiPhucTrangThai.Checked;

				

				str = this.cbTabBinhManPhuongThucUuTienMan.SelectedItem.ToString();
				int num5 = int.Parse(str.Substring(0, str.IndexOf(".")));
				string str4 = str.Substring(str.IndexOf(".") + 2);

				int num6 = int.Parse(this.txtTabBinhManQuanSoMin.Text);
				int num7 = int.Parse(this.txtTabBinhManMinSyKhi.Text);
				int num8 = int.Parse(this.txtTabBinhManMaxODi.Text);
				int num9 = int.Parse(this.txtTabBinhManTimeRun.Text);
				bool flag = this.chkTabBinhManTuNangSyKhi.Checked;

				int[] numArray5 = new int[4];
				int[] numArray = numArray5;
				numArray5 = new int[4];
				int[] numArray2 = numArray5;
				numArray5 = new int[4];
				int[] numArray3 = numArray5;
				numArray5 = new int[4];
				int[] numArray4 = numArray5;
				numArray[0] = int.Parse(this.txtTabBinhManQuanSoBoBinh.Text);
				numArray2[0] = int.Parse(this.txtTabBinhManQuanSoKyBinh.Text);
				numArray3[0] = int.Parse(this.txtTabBinhManQuanSoCungThu.Text);
				numArray4[0] = int.Parse(this.txtTabBinhManQuanSoXe.Text);


				str = this.cbTabBinhManQuanGioiBoBinh1.SelectedItem.ToString();
				numArray[1] = int.Parse(str.Substring(0, str.IndexOf(".")));
				str = this.cbTabBinhManQuanGioiBoBinh2.SelectedItem.ToString();
				numArray[2] = int.Parse(str.Substring(0, str.IndexOf(".")));
				str = this.cbTabBinhManQuanGioiBoBinh3.SelectedItem.ToString();
				numArray[3] = int.Parse(str.Substring(0, str.IndexOf(".")));

				str = this.cbTabBinhManQuanGioiKyBinh1.SelectedItem.ToString();
				numArray2[1] = int.Parse(str.Substring(0, str.IndexOf(".")));
				str = this.cbTabBinhManQuanGioiKyBinh2.SelectedItem.ToString();
				numArray2[2] = int.Parse(str.Substring(0, str.IndexOf(".")));
				str = this.cbTabBinhManQuanGioiKyBinh3.SelectedItem.ToString();
				numArray2[3] = int.Parse(str.Substring(0, str.IndexOf(".")));

				str = this.cbTabBinhManQuanGioiCungThu1.SelectedItem.ToString();
				numArray3[1] = int.Parse(str.Substring(0, str.IndexOf(".")));
				str = this.cbTabBinhManQuanGioiCungThu2.SelectedItem.ToString();
				numArray3[2] = int.Parse(str.Substring(0, str.IndexOf(".")));
				str = this.cbTabBinhManQuanGioiCungThu3.SelectedItem.ToString();
				numArray3[3] = int.Parse(str.Substring(0, str.IndexOf(".")));

				str = this.cbTabBinhManQuanGioiXe1.SelectedItem.ToString();
				numArray4[1] = int.Parse(str.Substring(0, str.IndexOf(".")));

                int mantype;
                if (rdBinhManDanhMan.Checked)       // ddanhs man
                    mantype = 1;
                else
                    mantype = 14;                   // ddanhs ddia tinh



                for (num10 = 0; num10 < this.chkTabBinhManTuongXuatTran.CheckedItems.Count; num10++)
                {
                    MilitaryGeneral general = (MilitaryGeneral)this.chkTabBinhManTuongXuatTran.CheckedItems[num10];

                    if (mantype == 1)
                    {
                        for (int i = 0; i < this.chkTabBinhManListManDanh.CheckedItems.Count; i++)
                        {
                            BinhManObj obj2 = new BinhManObj();
                            str = this.chkTabBinhManListManDanh.CheckedItems[i].ToString();

                            obj2.ManType = mantype;


                            obj2.ManID = int.Parse(str.Substring(0, str.IndexOf(".")));
                            obj2.ManName = str.Substring(str.IndexOf(".") + 2);
                            obj2.PhuongThucTanCongID = num3;
                            obj2.PhuongThucTanCongName = str2;
                            obj2.PhuongThucChonMucTieuID = num4;
                            obj2.PhuongThucChonMucTieuName = str3;
                            obj2.UuTienID = num5;
                            obj2.UuTienName = str4;
                            obj2.SoLuongQuanMinToGo = num6;
                            obj2.SiKhiMinToGo = num7;
                            obj2.MaxOToGo = num8;
                            obj2.TimeToCheck = num9;
                            obj2.TuUpSiKhi = flag;
                            obj2.GeneralId = general.GeneralId;
                            obj2.GeneralName = general.GeneralName;
                            obj2.CityID = general.CityID;
                            obj2.CityName = general.CityName;
                            obj2.CityID = id;
                            obj2.CityName = LVClient.Command.CityObj.City.AllCity[selectedIndex].name;
                            obj2.Military.Bobinh = numArray;
                            obj2.Military.KyBinh = numArray2;
                            obj2.Military.CungThu = numArray3;
                            obj2.Military.Xe = numArray4;

                            obj2.MuuKeTrongChienTranID = muuKeTrongChienTruongID;
                            obj2.MuuKeTrongChienTranName = muuKeTrongChienTruongName;
                            obj2.TuKhoiPhucTrangThai = tuKhoiPhucTrangThai;


                            BinhManList.Add(obj2);


                        } // end for chkTabBinhManListManDanh
                    } // end manty=1
                    else                // Danh dia tinh trong mo
                    {
                        BinhManObj obj2 = new BinhManObj();

                        obj2.ManType = mantype;
                        obj2.ToaDoMoX = int.Parse(txtBinhManToaDoMoX.Text);
                        obj2.ToaDoMoY = int.Parse(txtBinhManToaDoMoY.Text);


                        obj2.PhuongThucTanCongID = num3;
                        obj2.PhuongThucTanCongName = str2;
                        obj2.PhuongThucChonMucTieuID = num4;
                        obj2.PhuongThucChonMucTieuName = str3;
                        obj2.UuTienID = num5;
                        obj2.UuTienName = str4;
                        obj2.SoLuongQuanMinToGo = num6;
                        obj2.SiKhiMinToGo = num7;
                        obj2.MaxOToGo = num8;
                        obj2.TimeToCheck = num9;
                        obj2.TuUpSiKhi = flag;
                        obj2.GeneralId = general.GeneralId;
                        obj2.GeneralName = general.GeneralName;
                        obj2.CityID = general.CityID;
                        obj2.CityName = general.CityName;
                        obj2.CityID = id;
                        obj2.CityName = LVClient.Command.CityObj.City.AllCity[selectedIndex].name;
                        obj2.Military.Bobinh = numArray;
                        obj2.Military.KyBinh = numArray2;
                        obj2.Military.CungThu = numArray3;
                        obj2.Military.Xe = numArray4;

                        obj2.MuuKeTrongChienTranID = muuKeTrongChienTruongID;
                        obj2.MuuKeTrongChienTranName = muuKeTrongChienTruongName;
                        obj2.TuKhoiPhucTrangThai = tuKhoiPhucTrangThai;


                        BinhManList.Add(obj2);
                    }
                } //end for chkTabBinhManTuongXuatTran

				for (num10 = 0; num10 < this.chkTabBinhManTuongXuatTran.Items.Count; num10++)
				{
					this.chkTabBinhManTuongXuatTran.SetItemChecked(num10, false);
				}
				for (num10 = 0; num10 < this.chkTabBinhManListManDanh.Items.Count; num10++)
				{
					this.chkTabBinhManListManDanh.SetItemChecked(num10, false);
				}
				Common.common.LoadDataResultBinhMan(chkTabBinhManList);
			}
			catch (Exception)
			{
				MessageBox.Show("Sai cái gì đố rồi, xem lại đi");
			}
		}

		private void btTabBinhManHuyBo_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < this.chkTabBinhManList.CheckedItems.Count; i++)
			{
				BinhManList.Remove(this.chkTabBinhManList.CheckedItems[i]);
			}
			Common.common.LoadDataResultBinhMan(chkTabBinhManList);
		}

		private void chkAUTOBINHMAN_CheckedChanged(object sender, EventArgs e)
		{
			try
			{
				if (this.chkAUTOBINHMAN.Checked)
				{
                    if (BinhManList.Count > 0)
                    {
                        if (LVAUTOBINHMAN == null)
                        {
                            LVAUTOBINHMAN = new LVClient.LVThread.AUTOBINHMAN(this.lblAUTOBINHMANMESSAGE);
                        }

#if (!DEBUG)
                        // chan neu release
                        int count = 0;
                        while (count < BinhManList.Count)
                        {
                           

                            bool found = false;
                            BinhManObj bm = (BinhManObj)BinhManList[count];
                            for (int i = 0; i < chkTabBinhManListManDanh.Items.Count; i++)
                            {
                                string str = chkTabBinhManListManDanh.Items[i].ToString();

                                int ManID = int.Parse(str.Substring(0, str.IndexOf(".")));
                                if (ManID == bm.ManID)
                                {
                                    found = true;
                                    break;
                                }
                            }

                            if (!found)
                            {
                                count = 0;
                                BinhManList.Remove(bm);
                            }
                            count++;
                        }
#endif
                        if (BinhManList.Count > 0)
                        {
                            LVAUTOBINHMAN.GetParameter(BinhManList, (int.Parse(this.txtTabBinhManTimeRun.Text) * 60) * 0x3e8);
                            this.pnBinhMan.Enabled = false;
                            LVAUTOBINHMAN.Auto();
                        }
                        else
                        {
                            this.lblAUTOBINHMANMESSAGE.Text = "Chưa chọn đúng tham số";
                            this.chkAUTOBINHMAN.Checked = false;
                        }
                    }
                    else
                    {
                        this.lblAUTOBINHMANMESSAGE.Text = "Chưa chọn đúng tham số";
                        this.chkAUTOBINHMAN.Checked = false;
                    }
				}
				else
				{
					if (LVAUTOBINHMAN != null)
					{
						LVAUTOBINHMAN.Stop();
					}
					this.pnBinhMan.Enabled = true;
				}
			}
			catch (Exception ex)
			{
				this.lblAUTOBINHMANMESSAGE.Text = "Chưa chọn đúng tham số";
				this.chkAUTOBINHMAN.Checked = false;
			}
		}

		private void chkSKST_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void groupBox19_Enter(object sender, EventArgs e)
		{

		}

		private void chkThaoPhatBienCheThemQuan_CheckedChanged(object sender, EventArgs e)
		{
			txtThaoPhatBienCheBoBinhAmount.Enabled = chkThaoPhatBienCheThemQuan.Checked;
			txtThaoPhatBienCheKiBinhAmount.Enabled = chkThaoPhatBienCheThemQuan.Checked; 
			txtThaoPhatBienCheCungThuAmount.Enabled = chkThaoPhatBienCheThemQuan.Checked;
			txtThaoPhatBienCheXeAmount.Enabled = chkThaoPhatBienCheThemQuan.Checked;
		}

		private void btThaoPhatAddList_Click(object sender, EventArgs e)
		{
			try
			{
				//TuongDiThaoPhatList.Clear();
				int cityid = 0;

				for (int idx = 0; idx < cboGeneral.CheckedItems.Count; idx++)
				{
					LVClient.Common.GeneralThaoPhat TuongDiThaoPhat = new LVClient.Common.GeneralThaoPhat();


					TuongDiThaoPhat.CityID = ((LVClient.Command.CityObj.City)cboCity.SelectedItem).id;
					cityid = TuongDiThaoPhat.CityID;
					TuongDiThaoPhat.NhiemVuThaoPhatID = ((Command.CommonObj.ThaoPhat)cboNhiemVu.SelectedItem).id;
					TuongDiThaoPhat.timetorun = int.Parse(txtTPCHECK.Text);

					TuongDiThaoPhat.SiKhiMinToGo = int.Parse(txtThaoPhatSyKhi.Text);
					TuongDiThaoPhat.TuUpSiKhi = chkSKST.Checked;
					TuongDiThaoPhat.TuBienCheQuan = chkThaoPhatBienCheThemQuan.Checked;
					TuongDiThaoPhat.SoLuongQuanMinToGo = int.Parse(txtThaoPhatTongQuanMin.Text);

					TuongDiThaoPhat.soluongtuongdanh1tuongdich = int.Parse(cboThaoPhatSLTuongDanh1Dich.SelectedItem.ToString());

					string str = cboThaoPhatPhuongThucTanCong.SelectedItem.ToString();
					//str = str.Substring(0, str.IndexOf("."));
					TuongDiThaoPhat.PhuongThucTanCongID = int.Parse(str.Substring(0, str.IndexOf(".")));
					TuongDiThaoPhat.PhuongThucTanCongName = str.Substring(str.IndexOf(".") + 2);

					str = cboThaoPhatPhuongThucChonMucTieu.SelectedItem.ToString();
					//str = str.Substring(0, str.IndexOf("."));
					TuongDiThaoPhat.PhuongThucChonMucTieuID = int.Parse(str.Substring(0, str.IndexOf(".")));
					TuongDiThaoPhat.PhuongThucChonMucTieuName = str.Substring(str.IndexOf(".") + 2);

					str = cboThaoPhatMuuKeTrongChienTruong.SelectedItem.ToString();
					//str = str.Substring(0, str.IndexOf("."));
					TuongDiThaoPhat.MuuKeTrongChienTranID = int.Parse(str.Substring(0, str.IndexOf(".")));
					TuongDiThaoPhat.MuuKeTrongChienTranName = str.Substring(str.IndexOf(".") + 2);

					//
					TuongDiThaoPhat.TuDoiTranHinhKhac = chkThaoPhatTuDoiTranHinh.Checked;
					TuongDiThaoPhat.TuKhoiPhucTrangThai = chkThaoPhatTuKhoiPhucTrangThai.Checked;

					Command.CityObj.MilitaryGeneral gSelect = (Command.CityObj.MilitaryGeneral)cboGeneral.CheckedItems[idx];

					TuongDiThaoPhat.GeneralId = gSelect.GeneralId;
					TuongDiThaoPhat.GeneralName = gSelect.GeneralName;

					TuongDiThaoPhat.BienCheBoBinhAmount = int.Parse(txtThaoPhatBienCheBoBinhAmount.Text);
					TuongDiThaoPhat.BienCheKyBinhAmount = int.Parse(txtThaoPhatBienCheKiBinhAmount.Text);
					TuongDiThaoPhat.BienCheCungThuAmount = int.Parse(txtThaoPhatBienCheCungThuAmount.Text);
					TuongDiThaoPhat.BienCheXeAmount = int.Parse(txtThaoPhatBienCheXeAmount.Text);

					TuongDiThaoPhatList.Add(TuongDiThaoPhat);

				} //for (int idx = 0; idx < cboGeneral.CheckedItems.Count; idx++)

				if (TuongDiThaoPhatList.Count <= 0) return;
				for (int i = 0; i < TuongDiThaoPhatList.Count; i++)
				{
					if (((Common.GeneralThaoPhat)TuongDiThaoPhatList[i]).CityID != cityid)
					{
						MessageBox.Show("Các tướng thảo phạt phải cùng 1 thành/trại, xem lại đê", "Thảo phạt", MessageBoxButtons.OK, MessageBoxIcon.Error);
						TuongDiThaoPhatList.Clear();
						break;
					}

				}
				chklbThaoPhatListResult.Items.Clear();
				chklbThaoPhatListResult.Items.AddRange(TuongDiThaoPhatList.ToArray());

				

			}
			catch (Exception ex)
			{
				MessageBox.Show("Chưa cài đặt đúng cho thảo phạt, xem lại đê", "Thảo phạt", MessageBoxButtons.OK, MessageBoxIcon.Error);
			}
		}

		private void btThaoPhatHuyBo_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < this.chklbThaoPhatListResult.CheckedItems.Count; i++)
			{
				TuongDiThaoPhatList.Remove(this.chklbThaoPhatListResult.CheckedItems[i]);
			}
			chklbThaoPhatListResult.Items.Clear();
			chklbThaoPhatListResult.Items.AddRange(TuongDiThaoPhatList.ToArray());

		}

		private void comboBox9_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		private void textBox4_TextChanged(object sender, EventArgs e)
		{

		}

		private void checkBox4_CheckedChanged(object sender, EventArgs e)
		{

		}

		private void chkTabBinhManTuongXuatTran_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		

		private void cboCallManThanhTraiXuatQuan_SelectedIndexChanged(object sender, EventArgs e)
		{
			if (cboCallManThanhTraiXuatQuan.SelectedItem == null) return;

			chklbCallManTuongXuatTran.Items.Clear();
			LVClient.Command.CityObj.City city = (LVClient.Command.CityObj.City)cboCallManThanhTraiXuatQuan.SelectedItem;


			if (city.MilitaryGeneral == null) city.MilitaryGeneral = LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfo(city.id);

			if (city.MilitaryGeneral == null)
			{
				MessageBox.Show("Lỗi rồi, mạng lởm quá, chờ tý rồi thử lại đê.", "Mạng lởm quá");
				return;
			}

			chklbCallManTuongXuatTran.Items.AddRange(city.MilitaryGeneral);
		}

		private void btCallManCancel_Click(object sender, EventArgs e)
		{
			for (int i = 0; i < this.chklbCallManListResult.CheckedItems.Count; i++)
			{
				CallManList.Remove(this.chklbCallManListResult.CheckedItems[i]);
			}
			chklbCallManListResult.Items.Clear();
			chklbCallManListResult.Items.AddRange(CallManList.ToArray());
		}

		private void cbCallManBienCheQuanGioiCungThu3_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		private void btCallManXacNhan_Click(object sender, EventArgs e)
		{
			try
			{
				string str;
				//TuongDiThaoPhatList.Clear();
				int cityid = 0;

				for (int idx = 0; idx < chklbCallManTuongXuatTran.CheckedItems.Count; idx++)
				{
					LVClient.Command.CommonObj.CallManObj TuongDiDanhMan = new LVClient.Command.CommonObj.CallManObj();

					TuongDiDanhMan.GroupID = int.Parse(cbCallManGroup.SelectedItem.ToString());

					TuongDiDanhMan.CityID = ((LVClient.Command.CityObj.City)cboCallManThanhTraiXuatQuan.SelectedItem).id;
					cityid = TuongDiDanhMan.CityID;

					TuongDiDanhMan.TimeToCheck = int.Parse(txtCallManTimeToCheck.Text);
					TuongDiDanhMan.ToaDoCallVeX = int.Parse(txtCallManToaDoX.Text);
					TuongDiDanhMan.ToaDoCallVeY = int.Parse(txtCallManToaDoY.Text);

					TuongDiDanhMan.SiKhiMinToGo = int.Parse(txtCallManSyKhiMin.Text);
					TuongDiDanhMan.TuUpSiKhi = chkCallManTuNangSyKhi.Checked;
					TuongDiDanhMan.TuBienCheQuan = chkCallManCoBienCheThemQuan.Checked;
					TuongDiDanhMan.SoLuongQuanMinToGo = int.Parse(txtCallManQuanSoMin.Text);

					TuongDiDanhMan.Military.Bobinh[0] = int.Parse(txtCallManBienCheQuanBoBinh.Text);
					TuongDiDanhMan.Military.KyBinh[0] = int.Parse(txtCallManBienCheQuanKyBinh.Text);
					TuongDiDanhMan.Military.CungThu[0] = int.Parse(txtCallManBienCheQuanCungThu.Text);
					TuongDiDanhMan.Military.Xe[0] = int.Parse(txtCallManBienCheQuanXe.Text);


					str = this.cbCallManBienCheQuanGioiBoBinh1.SelectedItem.ToString();
					TuongDiDanhMan.Military.Bobinh[1] = int.Parse(str.Substring(0, str.IndexOf(".")));
					str = this.cbCallManBienCheQuanGioiBoBinh2.SelectedItem.ToString();
					TuongDiDanhMan.Military.Bobinh[2] = int.Parse(str.Substring(0, str.IndexOf(".")));
					str = this.cbCallManBienCheQuanGioiBoBinh3.SelectedItem.ToString();
					TuongDiDanhMan.Military.Bobinh[3] = int.Parse(str.Substring(0, str.IndexOf(".")));

					str = this.cbCallManBienCheQuanGioiKyBinh1.SelectedItem.ToString();
					TuongDiDanhMan.Military.KyBinh[1] = int.Parse(str.Substring(0, str.IndexOf(".")));
					str = this.cbCallManBienCheQuanGioiKyBinh2.SelectedItem.ToString();
					TuongDiDanhMan.Military.KyBinh[2] = int.Parse(str.Substring(0, str.IndexOf(".")));
					str = this.cbCallManBienCheQuanGioiKyBinh2.SelectedItem.ToString();
					TuongDiDanhMan.Military.KyBinh[3] = int.Parse(str.Substring(0, str.IndexOf(".")));

					str = this.cbCallManBienCheQuanGioiCungThu1.SelectedItem.ToString();
					TuongDiDanhMan.Military.CungThu[1] = int.Parse(str.Substring(0, str.IndexOf(".")));
					str = this.cbCallManBienCheQuanGioiCungThu2.SelectedItem.ToString();
					TuongDiDanhMan.Military.CungThu[2] = int.Parse(str.Substring(0, str.IndexOf(".")));
					str = this.cbCallManBienCheQuanGioiCungThu3.SelectedItem.ToString();
					TuongDiDanhMan.Military.CungThu[3] = int.Parse(str.Substring(0, str.IndexOf(".")));

					str = this.cbCallManBienCheQuanGioiXe11.SelectedItem.ToString();
					TuongDiDanhMan.Military.Xe[1] = int.Parse(str.Substring(0, str.IndexOf(".")));

					
					
					TuongDiDanhMan.SoTuongMinhDanh1TuongDich = int.Parse(cbCallManSLTuongMinhDanh1TuongDich.SelectedItem.ToString());


					str = cbCallManPhuongThucTanCong.SelectedItem.ToString();
					//str = str.Substring(0, str.IndexOf("."));
					TuongDiDanhMan.PhuongThucTanCongID = int.Parse(str.Substring(0, str.IndexOf(".")));
					TuongDiDanhMan.PhuongThucTanCongName = str.Substring(str.IndexOf(".") + 2);

					str = cbCallManPhuongThucChonMucTieu.SelectedItem.ToString();
					//str = str.Substring(0, str.IndexOf("."));
					TuongDiDanhMan.PhuongThucChonMucTieuID = int.Parse(str.Substring(0, str.IndexOf(".")));
					TuongDiDanhMan.PhuongThucChonMucTieuName = str.Substring(str.IndexOf(".") + 2);

					str = cbCallManMuuKeTrongChienTruong.SelectedItem.ToString();
					//str = str.Substring(0, str.IndexOf("."));
					TuongDiDanhMan.MuuKeTrongChienTranID = int.Parse(str.Substring(0, str.IndexOf(".")));
					TuongDiDanhMan.MuuKeTrongChienTranName = str.Substring(str.IndexOf(".") + 2);

					//
					TuongDiDanhMan.TuDoiTranHinhKhac = true; //chkCallManTuDoiTranHinh.Checked;
					TuongDiDanhMan.TuKhoiPhucTrangThai = chkCallManTuKhoiPhucTrangThai.Checked;
					TuongDiDanhMan.TuMuaManTocLenh = chkCallManTuMuaThemManTocLenh.Checked;

					Command.CityObj.MilitaryGeneral gSelect = (Command.CityObj.MilitaryGeneral)chklbCallManTuongXuatTran.CheckedItems[idx];

					TuongDiDanhMan.GeneralId = gSelect.GeneralId;
					TuongDiDanhMan.GeneralName = gSelect.GeneralName;

					

					if (cboCallManManCanCall.CheckedItems.Count == 0) return;



					LVClient.Command.CommonObj.ManOBJ manobj;
					for (int man = 0; man < cboCallManManCanCall.CheckedItems.Count; man++)
					{
						manobj = new ManOBJ();

						str = cboCallManManCanCall.CheckedItems[man].ToString();

						manobj.ManID = int.Parse(str.Substring(0, str.IndexOf(".")));
						manobj.ManName = str.Substring(str.IndexOf(".") + 2);

						TuongDiDanhMan.Mans.Add(manobj);
					}

					CallManList.Add(TuongDiDanhMan);

				} //for (int idx = 0; idx < cboGeneral.CheckedItems.Count; idx++)



				if (CallManList.Count > 0)
				{
					chklbCallManListResult.Items.Clear();
					chklbCallManListResult.Items.AddRange(CallManList.ToArray());
				}


			}
			catch (Exception ex)
			{
				MessageBox.Show("Chưa cài đặt đúng, xem lại đê", "Gọi man", MessageBoxButtons.OK, MessageBoxIcon.Error);
			}
		}

		private void tabMainTab_SelectedIndexChanged(object sender, EventArgs e)
		{

		}

		private void label103_Click(object sender, EventArgs e)
		{

		}

		private void textBox10_TextChanged(object sender, EventArgs e)
		{

		}

		private void chkCallManCoBienCheThemQuan_CheckedChanged(object sender, EventArgs e)
		{
			txtCallManBienCheQuanBoBinh.Enabled = chkCallManCoBienCheThemQuan.Checked;
			txtCallManBienCheQuanKyBinh.Enabled = chkCallManCoBienCheThemQuan.Checked; 
			txtCallManBienCheQuanCungThu.Enabled = chkCallManCoBienCheThemQuan.Checked; 
			txtCallManBienCheQuanXe.Enabled = chkCallManCoBienCheThemQuan.Checked;
		}

		private void chkAUTOCALLMAN_CheckedChanged(object sender, EventArgs e)
		{
			try
			{
				if (this.chkAUTOCALLMAN.Checked)
				{
					if (CallManList.Count > 0)
					{
						LVAUTOCALLMAN.GetParameter(CallManList, int.Parse(this.txtCallManTimeToCheck.Text) * 60 * 1000);
						this.pnCallMan.Enabled = false;
						LVAUTOCALLMAN.Auto();
					}
					else
					{
						this.lblAUTOCALLMANMESSAGE.Text = "Chưa chọn đúng tham số";
						this.chkAUTOCALLMAN.Checked = false;
					}
				}
				else
				{
					if (LVAUTOCALLMAN != null)
					{
						LVAUTOCALLMAN.Stop();
					}
					this.pnCallMan.Enabled = true;
				}
			}
			catch (Exception)
			{
				this.lblAUTOCALLMANMESSAGE.Text = "Chưa chọn đúng tham số";
				this.chkAUTOCALLMAN.Checked = false;
			}
		}

        private void tvDEL_AfterCheck(object sender, TreeViewEventArgs e)
        {
            foreach (TreeNode c in e.Node.Nodes)
            {
                c.Checked = e.Node.Checked;
            }

        }

        private void rdBinhManDanhMan_CheckedChanged(object sender, EventArgs e)
        {
            chkTabBinhManListManDanh.Visible = rdBinhManDanhMan.Checked;
            grBinhManToaDoMo.Visible = !rdBinhManDanhMan.Checked;
        }

        private void rdBinhManDanhDiaTinh_CheckedChanged(object sender, EventArgs e)
        {
            chkTabBinhManListManDanh.Visible = !rdBinhManDanhDiaTinh.Checked;
            grBinhManToaDoMo.Visible = rdBinhManDanhDiaTinh.Checked;
        }

		
		
		
		
	}

}

	


