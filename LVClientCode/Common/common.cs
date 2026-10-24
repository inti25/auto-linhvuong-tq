using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Data;
using System.Collections;
using System.IO;
using LVClient.Command.CommonObj;

namespace LVClient.Common {
    public class common 
	{
        public static Hashtable wepon = (Hashtable)JSON.JSON.JsonDecode("{\"ret\":0,\"list\":[[101,\"Thấu giáp thương\",0,15,0,0,0,2,2,8,1,8],[102,\"Hậu bối đao\",0,15,5,0,0,3,4,14,2,11],[103,\"Hổ bí đao\",0,15,10,0,0,5,7,25,3,14],[104,\"Cổ đồng đao\",0,15,15,0,0,9,12,44,6,18],[105,\"Đại khảm đao\",0,15,20,0,0,16,21,79,11,24],[106,\"Khoan nhận kiếm\",0,15,25,2000,0,29,38,142,19,31],[107,\"Tam hoàn đại đao\",256,15,30,0,0,51,68,255,34,41],[201,\"Thiết thai cung\",0,14,0,0,0,6,3,10,1,8],[202,\"Bá vương nỗ\",0,14,5,0,0,11,5,17,2,11],[203,\"Ly tần cung\",0,14,10,0,0,19,10,31,4,14],[204,\"Bảo điêu cung\",0,14,15,0,0,35,17,56,7,18],[205,\"Ngọc giác cung\",0,14,20,0,0,63,31,101,13,24],[206,\"Trường huyền giáp cung\",256,14,25,0,0,113,56,181,23,31],[207,\"Thần diên cung\",256,14,30,0,0,204,102,326,41,41]]}");
        public static void LoadCityToGridForVanchuyen(Panel tb) 
		{
            tb.Controls.Clear();
			Command.CityObj.City onecity;
			LVClient.Command.OPTObj.Vanchuyen vc;
			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) {
                onecity = Command.CityObj.City.AllCity[i];
				if (onecity.parentID == 0)
				{
				//if (onecity.id > 0) {
                    vc = new LVClient.Command.OPTObj.Vanchuyen();
                    vc.cboDesc.Items.AddRange(Command.CityObj.City.AllCity);
                    vc.cboSource.Items.AddRange(Command.CityObj.City.AllCity);
                    vc.Dock = DockStyle.Top;
                    vc.Height = 30;
                    tb.Controls.Add(vc);
                //}
				}
            }
        }
		public static void LoadCityToGridForAnUi(CheckedListBox chklstAnui)
		{
			
			LVClient.Command.CityObj.City city;
			bool check = false;
			chklstAnui.Items.Clear();
			for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
			{
				city = LVClient.Command.CityObj.City.AllCity[i];
				if (city.id > 0)
				{	check = false;	
					for (int j=0; j < LVClient.frmmain.AnuiForAuto.Count; j++)
						if (city.id == ((int) LVClient.frmmain.AnuiForAuto[j]))
						{
							check = true;
							break;
						}

					chklstAnui.Items.Add(city, check);
				}
			}

		}
		public static void LoadCityToGridForAnUi1(DataGridView dg)
		{
            DataSet tempds = new DataSet("temp");
            DataTable temptb = new DataTable("temp");
            DataColumn ID_TT = new DataColumn("ID_TT", typeof(int));
            DataColumn NAME_TT = new DataColumn("NAME_TT", typeof(string));
            DataColumn ADD_NK = new DataColumn("ADD_NK", typeof(bool));

            temptb.Columns.Add(ID_TT);
            temptb.Columns.Add(NAME_TT);
            temptb.Columns.Add(ADD_NK);

            for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) 
			{
                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                if (onecity.id > 0) 
				{
                    DataRow tempdr = temptb.NewRow();
                    tempdr["ID_TT"] = onecity.id;
                    tempdr["NAME_TT"] = onecity.name;
					for (int j = 0; j < LVClient.frmmain.AnuiForAuto.Count; j++)
					{
						if (int.Parse(LVClient.frmmain.AnuiForAuto[j].ToString()) == onecity.id )
							tempdr["ADD_NK"] = true;
						else
							tempdr["ADD_NK"] = false;
					}
                    
                    temptb.Rows.Add(tempdr);
                }
            }
			

            tempds.Tables.Add(temptb);

            dg.DataSource = tempds.Tables[0];
            dg.Columns[0].HeaderText = "ID";
            dg.Columns[0].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[0].ReadOnly = true;
            dg.Columns[0].Visible = false;

            dg.Columns[1].HeaderText = "Tên";
            dg.Columns[1].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[1].ReadOnly = true;
			dg.Columns[1].Width = "12345678901234567890".Length;

            dg.Columns[2].HeaderText = "Nhân khẩu";
            dg.Columns[2].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[2].ReadOnly = false;
        }

		private void cbHeader_OnCheckBoxClicked(object sender, PaintEventArgs e)
		{
			MessageBox.Show("sdsF");
		}

		public static void LoadDataResultForVCVK(ListBox lstVCVKResult)
		{
			lstVCVKResult.Items.Clear();
			Command.CommonObj.VanChuyenVK[] arVc = new LVClient.Command.CommonObj.VanChuyenVK[LVClient.frmmain.VanChuyenVuKhi.Count];

			for (int i = 0; i < LVClient.frmmain.VanChuyenVuKhi.Count; i++)
			{
				arVc[i] = (Command.CommonObj.VanChuyenVK)LVClient.frmmain.VanChuyenVuKhi[i];
			}

			lstVCVKResult.Items.AddRange(arVc);

		}

        public static void LoadCityToGridForSellResource(DataGridView dg) 
		{
            DataSet tempds = new DataSet("temp");			
            DataTable temptb = new DataTable("temp");


            DataColumn ID_TT = new DataColumn("ID_TT", typeof(int));
            DataColumn NAME_TT = new DataColumn("NAME_TT",typeof(string));
            DataColumn SELL_LUA = new DataColumn("SELL_LUA", typeof(bool));
            DataColumn SELL_GO = new DataColumn("SELL_GO", typeof(bool));
            DataColumn SELL_SAT = new DataColumn("SELL_SAT", typeof(bool));
            DataColumn SELL_DA = new DataColumn("SELL_DA", typeof(bool));

			/*
			DataGridViewCheckBoxColumn SELL_DA = new DataGridViewCheckBoxColumn();
			LVClient.Control.DatagridViewCheckBoxHeaderCell cbHeader = new LVClient.Control.DatagridViewCheckBoxHeaderCell();
			SELL_DA.HeaderCell = cbHeader;
			cbHeader.OnCheckBoxClicked +=
				new CheckBoxClickedHandler(cbHeader_OnCheckBoxClicked);
			//datagridview1.Columns.Add(colCB);
			*/

            temptb.Columns.Add(ID_TT);
            temptb.Columns.Add(NAME_TT);
            temptb.Columns.Add(SELL_LUA);
            temptb.Columns.Add(SELL_GO);
            temptb.Columns.Add(SELL_SAT);
            temptb.Columns.Add(SELL_DA);
			
			DataRow tempdr; 
        			
			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) 
			{
                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                if (onecity.id > 0) 
				{
                    tempdr = temptb.NewRow();
                    tempdr["ID_TT"] = onecity.id;
                    tempdr["NAME_TT"] = onecity.name;
                    tempdr["SELL_LUA"] = false;
                    tempdr["SELL_GO"] = false;
                    tempdr["SELL_SAT"] = false;
                    tempdr["SELL_DA"] = false;


					//lay data luu
					if (LVClient.frmmain.BanTaiNguyen.CityInfo != null)
						for (int j = 0; j < LVClient.frmmain.BanTaiNguyen.CityInfo.Length; j++)
							if (onecity.id == LVClient.frmmain.BanTaiNguyen.CityInfo[j].CityId)
							{
								tempdr["SELL_LUA"] = LVClient.frmmain.BanTaiNguyen.CityInfo[j].BanLua;
								tempdr["SELL_GO"] = LVClient.frmmain.BanTaiNguyen.CityInfo[j].BanGo;
								tempdr["SELL_SAT"] = LVClient.frmmain.BanTaiNguyen.CityInfo[j].BanSat;
								tempdr["SELL_DA"] = LVClient.frmmain.BanTaiNguyen.CityInfo[j].BanDa;
							}


                    temptb.Rows.Add(tempdr);
                }
            }

			//-----
			
			LVClient.frmmain.LVFRMMAIN.txtSELLCHECK.Text  = LVClient.frmmain.BanTaiNguyen.timetoruninminute.ToString();


			LVClient.frmmain.LVFRMMAIN.txtCOUNTLUA.Text =  LVClient.frmmain.BanTaiNguyen.LUA.SoLuongBan.ToString();
			LVClient.frmmain.LVFRMMAIN.txtSAFELUA.Text	 = LVClient.frmmain.BanTaiNguyen.LUA.SoLuongAnToan.ToString();

			LVClient.frmmain.LVFRMMAIN.txtBanTN_LUA_TB_Heso.Text = LVClient.frmmain.BanTaiNguyen.LUA.GiaTri.ToString();
			LVClient.frmmain.LVFRMMAIN.txtBanTN_LUA_TB_Heso.Enabled = true;
			if (LVClient.frmmain.BanTaiNguyen.LUA.LoaiBan == 1)		// co dinh
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_CODINH.Checked = true; 
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TB_Cong.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TB_Nhan.Enabled = false;	 				
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_THAPNHAT.Checked = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TRUNGBINH.Checked = false;
			}
			else
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TB_Cong.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TB_Nhan.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TB_Cong.Checked = !LVClient.frmmain.BanTaiNguyen.LUA.CongThucNhan;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TB_Nhan.Checked = LVClient.frmmain.BanTaiNguyen.LUA.CongThucNhan;
				if (LVClient.frmmain.BanTaiNguyen.LUA.LoaiBan == 2)		// trung binh
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TRUNGBINH.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_THAPNHAT.Checked = false;
				}
				else
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_THAPNHAT.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_LUA_TRUNGBINH.Checked = false;
				}
			}

			LVClient.frmmain.LVFRMMAIN.txtBanTN_GO_TB_Heso.Text = LVClient.frmmain.BanTaiNguyen.GO.GiaTri.ToString();
			LVClient.frmmain.LVFRMMAIN.txtBanTN_GO_TB_Heso.Enabled = true;
			if (LVClient.frmmain.BanTaiNguyen.GO.LoaiBan == 1)		// co dinh
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_CODINH.Checked = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TB_Cong.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TB_Nhan.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_THAPNHAT.Checked = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TRUNGBINH.Checked = false;
			}
			else
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TB_Cong.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TB_Nhan.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TB_Cong.Checked = !LVClient.frmmain.BanTaiNguyen.GO.CongThucNhan;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TB_Nhan.Checked = LVClient.frmmain.BanTaiNguyen.GO.CongThucNhan;
				if (LVClient.frmmain.BanTaiNguyen.GO.LoaiBan == 2)		// trung binh
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TRUNGBINH.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_THAPNHAT.Checked = false;
				}
				else
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_THAPNHAT.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_GO_TRUNGBINH.Checked = false;
				}
			}


			LVClient.frmmain.LVFRMMAIN.txtBanTN_DA_TB_Heso.Text = LVClient.frmmain.BanTaiNguyen.DA.GiaTri.ToString();
			LVClient.frmmain.LVFRMMAIN.txtBanTN_DA_TB_Heso.Enabled = true;
			if (LVClient.frmmain.BanTaiNguyen.DA.LoaiBan == 1)		// co dinh
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_CODINH.Checked = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TB_Cong.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TB_Nhan.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_THAPNHAT.Checked = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TRUNGBINH.Checked = false;
			}
			else
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TB_Cong.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TB_Nhan.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TB_Cong.Checked = !LVClient.frmmain.BanTaiNguyen.DA.CongThucNhan;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TB_Nhan.Checked = LVClient.frmmain.BanTaiNguyen.DA.CongThucNhan;
				if (LVClient.frmmain.BanTaiNguyen.DA.LoaiBan == 2)		// trung binh
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TRUNGBINH.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_THAPNHAT.Checked = false;
				}
				else
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_THAPNHAT.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_DA_TRUNGBINH.Checked = false;
				}
			}


			LVClient.frmmain.LVFRMMAIN.txtBanTN_SAT_TB_Heso.Text = LVClient.frmmain.BanTaiNguyen.SAT.GiaTri.ToString();
			LVClient.frmmain.LVFRMMAIN.txtBanTN_SAT_TB_Heso.Enabled = true;
			if (LVClient.frmmain.BanTaiNguyen.SAT.LoaiBan == 1)		// co dinh
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_CODINH.Checked = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TB_Cong.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TB_Nhan.Enabled = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_THAPNHAT.Checked = false;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TRUNGBINH.Checked = false;
			}
			else
			{
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TB_Cong.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TB_Nhan.Enabled = true;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TB_Cong.Checked = !LVClient.frmmain.BanTaiNguyen.SAT.CongThucNhan;
				LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TB_Nhan.Checked = LVClient.frmmain.BanTaiNguyen.SAT.CongThucNhan;
				if (LVClient.frmmain.BanTaiNguyen.SAT.LoaiBan == 2)		// trung binh
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TRUNGBINH.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_THAPNHAT.Checked = false;
				}
				else
				{
					LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_THAPNHAT.Checked = true;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_CODINH.Checked = false;
					LVClient.frmmain.LVFRMMAIN.rdBanTN_SAT_TRUNGBINH.Checked = false;
				}
			}




			//------


            tempds.Tables.Add(temptb);

            dg.DataSource = tempds.Tables[0];
            dg.Columns[0].HeaderText = "ID";
			dg.Columns[0].AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells;		//.DisplayedCells;
			
			dg.Columns[0].ReadOnly = true;
            dg.Columns[0].Visible = false;
            
            dg.Columns[1].HeaderText = "Tên";
			dg.Columns[1].AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells;	//DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[1].ReadOnly = true;
            
            dg.Columns[2].HeaderText = "Lúa";
            dg.Columns[2].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[2].ReadOnly = false;

            dg.Columns[3].HeaderText = "Gỗ";
            dg.Columns[3].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[3].ReadOnly = false;

            dg.Columns[4].HeaderText = "Sắt";
            dg.Columns[4].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[4].ReadOnly = false;

            dg.Columns[5].HeaderText = "Đá";
            dg.Columns[5].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[5].ReadOnly = false;
        }


        public static void LoadCityToGridForBuyResource(DataGridView dg) {
            DataSet tempds = new DataSet("temp");
            DataTable temptb = new DataTable("temp");
            DataColumn ID_TT = new DataColumn("ID_TT", typeof(int));
            DataColumn NAME_TT = new DataColumn("NAME_TT", typeof(string));
            DataColumn BUY_LUA = new DataColumn("BUY_LUA", typeof(bool));
            DataColumn BUY_GO = new DataColumn("BUY_GO", typeof(bool));
            DataColumn BUY_SAT = new DataColumn("BUY_SAT", typeof(bool));
            DataColumn BUY_DA = new DataColumn("BUY_DA", typeof(bool));

            temptb.Columns.Add(ID_TT);
            temptb.Columns.Add(NAME_TT);
            temptb.Columns.Add(BUY_LUA);
            temptb.Columns.Add(BUY_GO);
            temptb.Columns.Add(BUY_SAT);
            temptb.Columns.Add(BUY_DA);

            for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) {
                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                if (onecity.id > 0) {
                    DataRow tempdr = temptb.NewRow();
                    tempdr["ID_TT"] = onecity.id;
                    tempdr["NAME_TT"] = onecity.name;
                    tempdr["BUY_LUA"] = false;
                    tempdr["BUY_GO"] = false;
                    tempdr["BUY_SAT"] = false;
                    tempdr["BUY_DA"] = false;
                    temptb.Rows.Add(tempdr);
                }
            }

            tempds.Tables.Add(temptb);

            dg.DataSource = tempds.Tables[0];
            dg.Columns[0].HeaderText = "ID";
            dg.Columns[0].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[0].ReadOnly = true;
            dg.Columns[0].Visible = false;


            dg.Columns[1].HeaderText = "Tên";
			dg.Columns[1].AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells; //DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[1].ReadOnly = true;

            dg.Columns[2].HeaderText = "Lúa";
            dg.Columns[2].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[2].ReadOnly = false;

            dg.Columns[3].HeaderText = "Gỗ";
            dg.Columns[3].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[3].ReadOnly = false;

            dg.Columns[4].HeaderText = "Sắt";
            dg.Columns[4].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[4].ReadOnly = false;

            dg.Columns[5].HeaderText = "Đá";
            dg.Columns[5].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[5].ReadOnly = false;
        }
        public static void LoadCityToGridForMove(DataGridView dg) {
            DataSet tempds = new DataSet("temp");
            DataTable temptb = new DataTable("temp");
            DataColumn STT = new DataColumn("STT", typeof(int));
            DataColumn ID_TT = new DataColumn("ID_TT", typeof(int));
            DataColumn NAME_TT = new DataColumn("NAME_TT", typeof(string));
            DataColumn MOVE = new DataColumn("MOVE", typeof(bool));
            DataColumn X = new DataColumn("X", typeof(string));
            DataColumn Y = new DataColumn("Y", typeof(string));

            temptb.Columns.Add(STT);
            temptb.Columns.Add(ID_TT);
            temptb.Columns.Add(NAME_TT);
            temptb.Columns.Add(MOVE);
            temptb.Columns.Add(X);
            temptb.Columns.Add(Y);

            for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) {
                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                if (onecity.id < 0) {
                    DataRow tempdr = temptb.NewRow();
                    tempdr["STT"] = i;
                    tempdr["ID_TT"] = onecity.id;
                    tempdr["NAME_TT"] = onecity.name;
                    tempdr["MOVE"] = false;
                    tempdr["X"] = 0;
                    tempdr["Y"] = 0;
                    temptb.Rows.Add(tempdr);
                }
            }

            tempds.Tables.Add(temptb);

            dg.DataSource = tempds.Tables[0];

            dg.Columns[0].HeaderText = "STT";
            dg.Columns[0].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[0].ReadOnly = true;
            dg.Columns[0].Visible = false;

            dg.Columns[1].HeaderText = "ID";
            dg.Columns[1].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[1].ReadOnly = true;
            dg.Columns[1].Visible = false;


            dg.Columns[2].HeaderText = "Tên";
            dg.Columns[2].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[2].ReadOnly = true;

            dg.Columns[3].HeaderText = "Di chuyển";
            dg.Columns[3].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[3].ReadOnly = false;

            dg.Columns[4].HeaderText = "Tới (X)";
            dg.Columns[4].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[4].ReadOnly = false;

            dg.Columns[5].HeaderText = "Tới (Y)";
            dg.Columns[5].AutoSizeMode = DataGridViewAutoSizeColumnMode.DisplayedCells;
            dg.Columns[5].ReadOnly = false;
        }

	/*
	 * public static void LoadBuilding(int cityID)
		{
			Application.DoEvents();
			LVClient.Command.City.SwitchCitySlow(Command.CityObj.City.AllCity[i].id);
			Cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Command.CityObj.City.AllCity[i].id);

			LVClient.Command.City.GetAllBuilding(i, Cookies);

		}

	 */

		public static void LoadBuildingToTreeViewForbuild_(TreeView tv) {
            tv.Nodes.Clear();
            TreeNode root = tv.Nodes.Add("root", "Thành thị");
			string Cookies = "";
            for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) 
			{
				//Application.DoEvents();
				LVClient.Command.City.SwitchCitySlow(Command.CityObj.City.AllCity[i].id);
				Cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Command.CityObj.City.AllCity[i].id);
				
				LVClient.Command.City.GetAllBuilding(i, false, Cookies);

                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                TreeNode tt = root.Nodes.Add(onecity.id.ToString(), onecity.name);
                for (int j = 0; j < onecity.AllBuilding.Length; j++) {
					//Application.DoEvents();
                    Command.CityObj.Building onebuilding = onecity.AllBuilding[j];
                    //int pid, int gid, int tid
                    tt.Nodes.Add(onebuilding.pid.ToString() + "." + onebuilding.gid.ToString() + "." + onecity.id.ToString(), onebuilding.name + " (" + onebuilding.level + ")");
                }
            }
        }
		public static void LoadBuildingToTreeViewForbuild_(TreeView tv, int citypost)
		{
			try
			{
				tv.Nodes.Clear();
				//TreeNode root = tv.Nodes.Add("root", "Thành thị");


				int count = 0;
				string Cookies = "";

				//Application.DoEvents();
				LVClient.Command.City.SwitchCitySlow(Command.CityObj.City.AllCity[citypost].id);
				Cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Command.CityObj.City.AllCity[citypost].id);

				while (count < 5)
				{

					LVClient.Command.City.GetAllBuilding(citypost, false, Cookies);
					count++;
					if (Command.CityObj.City.AllCity[citypost].AllBuilding != null) break;

					System.Threading.Thread.Sleep(2000);
				}

				Command.CityObj.City onecity = Command.CityObj.City.AllCity[citypost];


				//TreeNode tt = root.Nodes.Add(onecity.id.ToString(), onecity.name);
				TreeNode tt = tv.Nodes.Add(onecity.id.ToString(), onecity.name);



				
				for (int j = 0; j < onecity.AllBuilding.Length; j++)
				{
					//Application.DoEvents();
					Command.CityObj.Building onebuilding = onecity.AllBuilding[j];
					//int pid, int gid, int tid
					tt.Nodes.Add(onebuilding.pid.ToString() + "." + onebuilding.gid.ToString() + "." + onecity.id.ToString(), onebuilding.name + " (" + onebuilding.level + ")");
				}

				TreeNode root = tv.Nodes[0];

				root.ExpandAll();
				//if (root.Checked) IsBuildAll = true;
				for (int i = 0; i < root.Nodes.Count; i++)
				{
					root.Nodes[i].Checked = Command.CityObj.City.AllCity[citypost].AllBuilding[i].isUp;
				}			


			}
			catch (Exception ex)
			{
			}
			
		}
        public static void LoadBuildingToTreeViewForbuild(TreeView tv) 
		{
            tv.Nodes.Clear();
            TreeNode root = tv.Nodes.Add("root", "Thành thị");

            for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) 
			{
                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                TreeNode tt = root.Nodes.Add(onecity.id.ToString(), onecity.name);
                for (int j = 0; j < onecity.AllBuilding.Length; j++) 
				{
                    Command.CityObj.Building onebuilding = onecity.AllBuilding[j];
                    //int pid, int gid, int tid
                    tt.Nodes.Add(onebuilding.pid.ToString() + "." + onebuilding.gid.ToString() + "." + onecity.id.ToString(), onebuilding.name + " (" + onebuilding.level + ")");
                }
            }
            root.ExpandAll();
            
        }

		public static bool LoadGeneralForUpSiKhi(TreeView tv)
		{
			return LoadGeneralForUpSiKhi(tv, false); 
		}
        public static bool LoadGeneralForUpSiKhi(TreeView tv, bool reload) 
		{
			try
			{
				tv.Nodes.Clear();
				TreeNode root = tv.Nodes.Add("root", "Tướng");
				Command.CityObj.City onecity;
				Command.CityObj.MilitaryGeneral onegeneral;

				if (reload) LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfoIntoCity();

				
				for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
				{
					onecity = Command.CityObj.City.AllCity[i];
					//LVClient.Command.City.SwitchCitySlow(onecity.id);

					//Command.Common.GetGeneral(i, reload);
					

					string status;
					if (onecity.MilitaryGeneral != null)
					{
						for (int j = 0; j < onecity.MilitaryGeneral.Length; j++)
						{
							if (onecity.MilitaryGeneral[j] != null)
							{
								onegeneral = onecity.MilitaryGeneral[j];
								//int pid, int gid, int tid

								status = "";
								if (onegeneral.GeneralStatus != 0)
									status = " (" + LVClient.Command.CityObj.General.GetTrangThaiName(onegeneral.GeneralStatus) + ")";



								root.Nodes.Add(onecity.id + "." + onegeneral.GeneralId,   onecity.name + " - " + onegeneral.GeneralName 
									+ status );
								
							}
						}
					}
				}

				return true;
			}
			catch (Exception ex)
			{
				return false;
			}

        }

		public static bool LoadGeneralForBienChe(TreeView tv)
		{
			try
			{
				tv.Nodes.Clear();
				//TreeNode root = tv.Nodes.Add("root", "Tướng");
				string str ="";
				
				LVClient.Common.BienChe oneBienChe;
				for (int i = 0; i <  LVClient.frmmain.ListBienChe.Count  ; i++)
				{
					str = "";
					oneBienChe = (LVClient.Common.BienChe) LVClient.frmmain.ListBienChe[i];
					str += "Biên chế: " + oneBienChe.bobinhamount + " bộ,";
					str += oneBienChe.kybinhamount + " kỵ,";
					str += oneBienChe.cungthuamount + " cung,";
					str += oneBienChe.xemount+ " xe,";
					if (oneBienChe.nangsykhi)
						str += " có nâng SK.";
					else
						str += " không nâng SK.";

 
					tv.Nodes.Add(oneBienChe.generalid.ToString(), oneBienChe.cityname + ":  " +   oneBienChe.generalname + " - " + str ); 
				}
					
				return true;
			}
			catch (Exception ex)
			{
				return false;
			}

		}

		public static void LoadDataResultBinhMan(ListBox chklBinhManListResult)
		{
			chklBinhManListResult.Items.Clear();
			BinhManObj[] items = new BinhManObj[LVClient.frmmain.BinhManList.Count];
			for (int i = 0; i < LVClient.frmmain.BinhManList.Count; i++)
			{
				items[i] = (BinhManObj)LVClient.frmmain.BinhManList[i];
			}
			chklBinhManListResult.Items.AddRange(items);
		}


        public static void LoadDataForThaoPhat(ArrayList artuongdithaophat) 
		{
		
			int count = 0;
			while (true && count < 5)
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

			if (Command.CityObj.City.AllCity == null) LVClient.Command.City.UpdateAllSimpleCity();
			if (Command.CityObj.City.AllCity == null) return;

			LVClient.frmmain.LVFRMMAIN.cboCity.Items.Clear();
			LVClient.frmmain.LVFRMMAIN.cboCity.Items.AddRange(Command.CityObj.City.AllCity);

			LVClient.frmmain.LVFRMMAIN.cboNhiemVu.Items.Clear();
			LVClient.frmmain.LVFRMMAIN.cboNhiemVu.Items.AddRange(Command.CommonObj.ThaoPhat.AllNhiemVu);

			string str = "";


			Common.GeneralThaoPhat gen;
			if (artuongdithaophat != null && artuongdithaophat.Count > 0)
			{
				gen = (Common.GeneralThaoPhat)artuongdithaophat[0];
				for (int i = 0; i < LVClient.frmmain.LVFRMMAIN.cboCity.Items.Count; i++)
					if (((Command.CityObj.City)LVClient.frmmain.LVFRMMAIN.cboCity.Items[i]).id == gen.CityID)
					{
						LVClient.frmmain.LVFRMMAIN.cboCity.SelectedIndex = i;
						break;
					}

				for (int i = 0; i < LVClient.frmmain.LVFRMMAIN.cboNhiemVu.Items.Count; i++)
					if (((Command.CommonObj.ThaoPhat)LVClient.frmmain.LVFRMMAIN.cboNhiemVu.Items[i]).id == gen.NhiemVuThaoPhatID)
					{
						LVClient.frmmain.LVFRMMAIN.cboNhiemVu.SelectedIndex = i;
						break;
					}

				for (int j = 0; j < LVClient.frmmain.LVFRMMAIN.cboThaoPhatSLTuongDanh1Dich.Items.Count; j++)
				{
					str = LVClient.frmmain.LVFRMMAIN.cboThaoPhatSLTuongDanh1Dich.Items[j].ToString();
					//str = str.Substring(0, str.IndexOf("."));
					if (gen.soluongtuongdanh1tuongdich == int.Parse(str))
					{
						LVClient.frmmain.LVFRMMAIN.cboThaoPhatSLTuongDanh1Dich.SelectedIndex = j;
						break;
					}
				}

				for (int j = 0; j < LVClient.frmmain.LVFRMMAIN.cboThaoPhatPhuongThucTanCong.Items.Count; j++)
				{
					str = LVClient.frmmain.LVFRMMAIN.cboThaoPhatPhuongThucTanCong.Items[j].ToString();
					str = str.Substring(0, str.IndexOf("."));
					if (gen.PhuongThucTanCongID == int.Parse(str))
					{
						LVClient.frmmain.LVFRMMAIN.cboThaoPhatPhuongThucTanCong.SelectedIndex = j;
						break;
					}
				}

				for (int j = 0; j < LVClient.frmmain.LVFRMMAIN.cboThaoPhatPhuongThucChonMucTieu.Items.Count; j++)
				{
					str = LVClient.frmmain.LVFRMMAIN.cboThaoPhatPhuongThucChonMucTieu.Items[j].ToString();
					str = str.Substring(0, str.IndexOf("."));
					if (gen.PhuongThucChonMucTieuID == int.Parse(str))
					{
						LVClient.frmmain.LVFRMMAIN.cboThaoPhatPhuongThucChonMucTieu.SelectedIndex = j;
						break;
					}
				}
				for (int j = 0; j < LVClient.frmmain.LVFRMMAIN.cboThaoPhatMuuKeTrongChienTruong.Items.Count; j++)
				{
					str = LVClient.frmmain.LVFRMMAIN.cboThaoPhatMuuKeTrongChienTruong.Items[j].ToString();
					str = str.Substring(0, str.IndexOf("."));
					if (gen.MuuKeTrongChienTranID == int.Parse(str))
					{
						LVClient.frmmain.LVFRMMAIN.cboThaoPhatMuuKeTrongChienTruong.SelectedIndex = j;
						break;
					}
				}

				LVClient.frmmain.LVFRMMAIN.txtTPCHECK.Text = gen.timetorun.ToString();
				LVClient.frmmain.LVFRMMAIN.txtThaoPhatSyKhi.Text = gen.SiKhiMinToGo.ToString();
				LVClient.frmmain.LVFRMMAIN.chkSKST.Checked = gen.TuUpSiKhi;
				LVClient.frmmain.LVFRMMAIN.chkThaoPhatBienCheThemQuan.Checked = gen.TuBienCheQuan;
				LVClient.frmmain.LVFRMMAIN.txtThaoPhatBienCheBoBinhAmount.Text = gen.BienCheBoBinhAmount.ToString();
				LVClient.frmmain.LVFRMMAIN.txtThaoPhatBienCheKiBinhAmount.Text = gen.BienCheKyBinhAmount.ToString();
				LVClient.frmmain.LVFRMMAIN.txtThaoPhatBienCheCungThuAmount.Text = gen.BienCheCungThuAmount.ToString();
				LVClient.frmmain.LVFRMMAIN.txtThaoPhatBienCheXeAmount.Text = gen.BienCheXeAmount.ToString();

				LVClient.frmmain.LVFRMMAIN.txtThaoPhatTongQuanMin.Text = gen.SoLuongQuanMinToGo.ToString();
				LVClient.frmmain.LVFRMMAIN.chkThaoPhatTuKhoiPhucTrangThai.Checked = gen.TuKhoiPhucTrangThai;
				
			}


			Command.CityObj.City city = (Command.CityObj.City)LVClient.frmmain.LVFRMMAIN.cboCity.SelectedItem;
			if (city != null)
			{
				if (city.MilitaryGeneral == null) LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfoIntoCity();
				if (city.MilitaryGeneral == null) return;

				LVClient.frmmain.LVFRMMAIN.cboGeneral.Items.Clear();

				LVClient.frmmain.LVFRMMAIN.cboGeneral.Items.AddRange(city.MilitaryGeneral);

				int g;
				for (int i = 0; i < LVClient.frmmain.LVFRMMAIN.cboGeneral.Items.Count; i++)
				{
					g = ((Command.CityObj.MilitaryGeneral)LVClient.frmmain.LVFRMMAIN.cboGeneral.Items[i]).GeneralId;
					for (int k = 0; k < artuongdithaophat.Count; k++)
					{
		
						gen = (Common.GeneralThaoPhat)artuongdithaophat[k];
						if (g == gen.GeneralId)
						{
							LVClient.frmmain.LVFRMMAIN.cboGeneral.SetItemChecked(i, true);
						}
					}
				}

				LVClient.frmmain.LVFRMMAIN.ThaoPhat_loaded = true;
			}

			LVClient.frmmain.LVFRMMAIN.chklbThaoPhatListResult.Items.Clear();
			LVClient.frmmain.LVFRMMAIN.chklbThaoPhatListResult.Items.AddRange(LVClient.frmmain.TuongDiThaoPhatList.ToArray());

			
		}


        public static void LoadUpgradeToTreeViewForUpdate(TreeView tv) {
            tv.Nodes.Clear();
            TreeNode root = tv.Nodes.Add("root", "Đại học điện");
            TreeNode tn = root.Nodes.Add("tn", "Tài nguyên");
            tn.Nodes.Add(1.ToString(), "Trồng trọt");
            tn.Nodes.Add(2.ToString(), "Luyện sắt");
            tn.Nodes.Add(3.ToString(), "Đào đá");
            tn.Nodes.Add(4.ToString(), "Chặt gỗ");
            TreeNode bb = root.Nodes.Add("bb", "Bộ binh");
            bb.Nodes.Add(24.ToString(), "Hành quân");
            bb.Nodes.Add(25.ToString(), "Mưu lược");
            bb.Nodes.Add(26.ToString(), "Kháng cung");
            bb.Nodes.Add(27.ToString(), "Chiến giáp");
            TreeNode kb = root.Nodes.Add("kb", "Kỵ binh");
            kb.Nodes.Add(20.ToString(), "Hành quân");
            kb.Nodes.Add(21.ToString(), "Mưu lược");
            kb.Nodes.Add(22.ToString(), "Kháng bộ");
            kb.Nodes.Add(23.ToString(), "Chiến mã");
            TreeNode ct = root.Nodes.Add("ct", "Cung thủ");
            ct.Nodes.Add(16.ToString(), "Hành quân");
            ct.Nodes.Add(17.ToString(), "Mưu lược");
            ct.Nodes.Add(18.ToString(), "Kháng kỵ");
            ct.Nodes.Add(19.ToString(), "Cung tiến");
            TreeNode qg = root.Nodes.Add("qg", "Quân giới");
            qg.Nodes.Add(12.ToString(), "Chiến mã");
            qg.Nodes.Add(13.ToString(), "Khôi giáp");
            qg.Nodes.Add(14.ToString(), "Cung tiễn");
            qg.Nodes.Add(15.ToString(), "Vũ khí");
            TreeNode k = root.Nodes.Add("k", "Khác");
            k.Nodes.Add(5.ToString(), "Mưu lược");
            k.Nodes.Add(6.ToString(), "Do thám");
            k.Nodes.Add(7.ToString(), "Thống lĩnh");
            k.Nodes.Add(8.ToString(), "Trận pháp");
            k.Nodes.Add(9.ToString(), "Doanh trại");
            k.Nodes.Add(10.ToString(), "Tích trữ");
            k.Nodes.Add(11.ToString(), "Xây thành");
            k.Nodes.Add(28.ToString(), "Vỗ về dân");
            k.Nodes.Add(29.ToString(), "Tường thành");

			
			//UpgradeForAuto.Add(((LVClient.Command.CityObj.City)cboCityForUpgrade.SelectedItem).id);
				TreeNode r = tv.Nodes["root"];
				foreach (TreeNode t in r.Nodes)
				{
					foreach (TreeNode c in t.Nodes)
					{

						for (int i = 1; i < LVClient.frmmain.UpgradeForAuto.Count; i++)
						{
							if (c.Name == LVClient.frmmain.UpgradeForAuto[i].ToString())
							{
								c.Checked = true;
							}

						}
					}
				}			
        }
        public static void LoadDoanhTraiForMove(Panel pn) {
            pn.Controls.Clear();
            for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++) {
                Command.CityObj.City onecity = Command.CityObj.City.AllCity[i];
                if (onecity.id < 0) 
				{
                    LVClient.Command.CommonObj.doitrai vc = new LVClient.Command.CommonObj.doitrai();
                    vc.txtTen.Text = onecity.name;
                    vc.id = onecity.id; ;
                    vc.Dock = DockStyle.Top;
                    vc.Height = 29;
                    pn.Controls.Add(vc);
                }
            }
        }
        public static int LoadCityForBuyWepon(Panel pn) 
		{
			try
			{
				LVClient.Command.OPTObj.wepon vc;
				pn.Controls.Clear();
				Command.CityObj.City onecity;

				for (int i = Command.CityObj.City.AllCity.Length -1; i >=0 ; i--)
				{
					onecity = Command.CityObj.City.AllCity[i];
					if (onecity == null) continue;
					if (onecity.id > 0)
					{
						vc = new LVClient.Command.OPTObj.wepon();
						
						Application.DoEvents();

						if (onecity.AllBuilding == null)
							LVClient.Command.City.GetAllBuilding(i, false, 
								LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(onecity.id));

						if (onecity.AllBuilding != null)
						{

							//Lay nha vu khi
							for (int j = 0; j < onecity.AllBuilding.Length; j++)
							{
								if (onecity.AllBuilding[j] != null)
								{

#if (DEBUG)
                                    if (onecity.AllBuilding[j].gid == 13 || onecity.AllBuilding[j].gid == 66)
#else
									if (onecity.AllBuilding[j].gid == 13)                       // binh khí
#endif	
                                    {
										vc.posid_w = onecity.AllBuilding[j].pid;
									}

#if (DEBUG)
                                    if (onecity.AllBuilding[j].gid == 14 || onecity.AllBuilding[j].gid == 67)
#else
									if (onecity.AllBuilding[j].gid == 14)                       // khôi giáp
#endif

                                    {
										vc.posid_a = onecity.AllBuilding[j].pid;
									}


#if (DEBUG)
                                    if (onecity.AllBuilding[j].gid == 15 || onecity.AllBuilding[j].gid == 68)
#else
									 if (onecity.AllBuilding[j].gid == 15)                       // mã xa
#endif
                                    {
										vc.posid_h = onecity.AllBuilding[j].pid;
									}

									//if (vc.posid_w != 0 || vc.posid_a != 0 || vc.posid_h != 0) break;

									Application.DoEvents();
								}
							}
						}
						else
						{
							vc.posid_w = -1;
						}

						if (vc.posid_w != 0 || vc.posid_a != 0 || vc.posid_h != 0)
						{
							vc.lblCityName.Text = onecity.name;
							vc.cityid = onecity.id;
							vc.Dock = DockStyle.Top;
							vc.Height = 29;
							pn.Controls.Add(vc);
						}
					}
				}
				return 0;
			}
			catch (Exception ex)
			{
				return 1;
			}

        }

		public static void LoadDataForVCVK(Panel pn)
		{
			   
		}
		public static void LoadDataResultForVCVK()
		{
		}

        public static int[] NextPoint(int x1, int y1, int x2, int y2, int step) {
            int d, ax, ay, sx, sy, dx, dy, cstep;
            cstep = 0;

            dx = x2 - x1;
            ax = Math.Abs(dx) << 1;
            if (dx < 0) sx = -1; else sx = 1;

            dy = y2 - y1;
            ay = Math.Abs(dy) << 1;
            if (dy < 0) sy = -1; else sy = 1;

            if (ax > ay) {
                d = ay - (ax >> 1);
                while (x1 != x2) {
                    if (d >= 0) {
                        y1 = y1 + sy;
                        d = d - ax;
                    }

                    x1 = x1 + sx;
                    d = d + ay;
                    cstep++;
                    if (cstep == step) break;
                } //while
            } else {
                d = ax - (ay >> 1);
                while (y1 != y2) {
                    if (d >= 0) {
                        x1 = x1 + sx;
                        d = d - ay;
                    }
                    y1 = y1 + sy;
                    d = d + ax;
                    cstep++;
                    if (cstep == step) break;
                } //while
            } //if
            int[] r = new int[] { x1, y1 };
            return r;
        }


		public static int distancefrom2poin(int x1, int y1, int x2, int y2)
		{
			int d = (int) Math.Floor( (Math.Sqrt( (x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))));
			return d;
		}
			

        public static void ClearCookies() {
            DirectoryInfo d = new DirectoryInfo(Environment.GetFolderPath(Environment.SpecialFolder.Cookies));
            FileInfo[] f = d.GetFiles();
            foreach (FileInfo fi in f) {
                if (fi.Name.IndexOf("linhvuong.zooz") > -1) {
                    try {
                        fi.Delete();
                    } catch (Exception ex) {
                        //MessageBox.Show(ex.ToString());
                    }
                }
            }
        }


		public static int MapIDtoY(int mapID)
		{
			int y = 0;
			y = 656 - (int)Math.Floor((decimal)((mapID - 1) / 1313));
			return y;
		}

		public static int MapIDtoX(int mapID)
		{
			int x = 0; x = (mapID - 1) % 1313 - 656;
			return x;
		}
		public static int MapPosToMapID(int x, int y)
		{
			int mapID = 0;
			mapID = (656 + x) + (656 - y) * 1313 + 1;
			return mapID;
		}

    }
}
