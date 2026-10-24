using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;

namespace LVClient.Command {
    public class Common 
	{
		private static Object GeneralisLock = new Object();

        public static Hashtable Execute(int command, string parameter,bool wait) {
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/Common.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
            header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Connection: keep-alive\n";
            header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/city\n";
            header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            Hashtable response = Web.LVWeb.SendAndReceive(header + data, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, wait);
            if (wait) 
			{
                try {
                    Hashtable t = (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
                    return t;
                }catch(Exception ex)
				{
                    return null;
                }
            } else 
			{
				if (response == null || response["DATA"] == null) return null;

				Hashtable t = new Hashtable();
				t.Add("DATA", response["DATA"].ToString());
				return  t;
            }
        }
        public static Hashtable Execute(int command, string parameter, bool wait, string cookies ) {
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/Common.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
            header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Connection: keep-alive\n";
            header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/city\n";
            header += "Cookie: " + cookies + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            Hashtable response = Web.LVWeb.SendAndReceive(header + data, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, wait);
            if (wait) 
			{
				if (response != null &&  response["DATA"] != null)
					return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
				else
					return null;
			} else 
			{
                return null;
            }
        }
        public static Hashtable GetCityAttack(int id, string cookies) 
		{
            Hashtable r = Execute(41, "lCityCampID="+id, true, cookies);
            //{"ret":0,"list":[[25547,"Âm Phong Thực Cốt",192433,4242485,[[1,3,29,1,45632],[12,3,30,1,313803],[22,3
            //,29,1,39808]],[],[],-1]],"tech":[7,23,62765],"task":[0,"",0,0]}
            return r;
        }
        public static Hashtable GetCityAttack() {
            Hashtable r = Execute(41, "lCityCampID=0", true);
            //{"ret":0,"list":[[25547,"Âm Phong Thực Cốt",192433,4242485,[[1,3,29,1,45632],[12,3,30,1,313803],[22,3
            //,29,1,39808]],[],[],-1]],"tech":[7,23,62765],"task":[0,"",0,0]}
            return r;
        }
        public static Hashtable GetGeneralMilitary(int generalid) 
		{
			/*
            string parameter = "";
			parameter += "lGeneralID=" + generalid;
            parameter += "&lCityID=" + 0;
            return Execute(12, parameter, true);
			 */
			return GetGeneralMilitary(0, generalid);
        }

		public static Hashtable GetGeneralMilitary(int cityid, int generalid)
		{
			string parameter = "";
			parameter += "lGeneralID=" + generalid;
			parameter += "&lCityID=" + cityid;
			return Execute(12, parameter, true);
		}

		/// <summary>
		/// Lấy thông tin về tướng. Chỉ lấy thông tin về quân số và vũ khí, không lấy được sỹ khí 
		/// </summary>
		/// <param name="cityid"></param>
		/// <param name="generalid"></param>
		/// <returns></returns>
		public static LVClient.Command.CityObj.MilitaryGeneral GetGeneralMilitaryInfo(int cityid, int generalid)
		{
			try
			{
				LVClient.Command.CityObj.MilitaryGeneral onegenaral = new LVClient.Command.CityObj.MilitaryGeneral();
				//string parameter = "";
				//parameter += "lGeneralID=" + generalid;
				//parameter += "&lCityID=" + cityid;
				//Hashtable ret= Execute(12, parameter, true);

				Hashtable ret = GetGeneralMilitary(cityid, generalid);
				
				if (ret == null) return null;

				/*{"ret":0,"infantry_equip":[2975,305,"Thiên h? giáp",305,"Thiên h? giáp",305,"Thiên h? giáp",10,662,569,1026,10],
				"cavalry_equip":[0,403,"Bôn tiêu mã",105,"Ð?i kh?m dao",305,"Thiên h? giáp",69,433,260,263,41],
				"bowman_equip":[2472,250,"Nguu giác cung",250,"Nguu giác cung",205,"Ng?c giác cung",259,129,281,158,17],
				"mangonel":[501,"Xe ném dá lo?i nh?",0,13,30,23,25,15],"battle_array":4,"ratio_attack":0,"ratio_PK":100,"ratio_stratagem":0,
				"withdraw_loss":10,"withdraw_morale":10,"owner_city_id":12933,"partner_id":447531,"partner_name":"Viên Ðoan Minh"}
				  */


				ArrayList arTemp = ((ArrayList)ret["infantry_equip"]);
				onegenaral.Military.Bobinh[0] = int.Parse(arTemp[0].ToString());  // so luong bo binh hien co
				onegenaral.Military.Bobinh[1] = int.Parse(arTemp[1].ToString());	// loai vu khi 1
				onegenaral.Military.Bobinh[2] = int.Parse(arTemp[3].ToString());
				onegenaral.Military.Bobinh[3] = int.Parse(arTemp[5].ToString());

				arTemp = ((ArrayList)ret["cavalry_equip"]);
				onegenaral.Military.KyBinh[0] = int.Parse(arTemp[0].ToString());   // so luong ky binh hien co
				onegenaral.Military.KyBinh[1] = int.Parse(arTemp[1].ToString());	// loai vu khi 1
				onegenaral.Military.KyBinh[2] = int.Parse(arTemp[3].ToString());
				onegenaral.Military.KyBinh[3] = int.Parse(arTemp[5].ToString());

				arTemp = (((ArrayList)ret["bowman_equip"]));
				onegenaral.Military.CungThu[0] = int.Parse(arTemp[0].ToString());   // so luong cung hien co
				onegenaral.Military.CungThu[1] = int.Parse(arTemp[1].ToString());	// loai vu khi 1
				onegenaral.Military.CungThu[2] = int.Parse(arTemp[3].ToString());
				onegenaral.Military.CungThu[3] = int.Parse(arTemp[5].ToString());

				arTemp = (((ArrayList)ret["mangonel"]));
				onegenaral.Military.Xe[0] = int.Parse(arTemp[2].ToString());   // so luong xe hien co
				onegenaral.Military.Xe[1] = int.Parse(arTemp[0].ToString());	// loai vu khi 1
				//onegenaral.Military.Xe[2]int.Parse(arTemp[3]);
				//onegenaral.Military.Xe[3]int.Parse(arTemp[5];


				onegenaral.Military.TranHinh = int.Parse(ret["battle_array"].ToString());
				onegenaral.Military.RatioAttack = int.Parse(ret["ratio_attack"].ToString());
				onegenaral.Military.RatioPK = int.Parse(ret["ratio_PK"].ToString());
				onegenaral.Military.RatioStratagem = int.Parse(ret["ratio_stratagem"].ToString());
				onegenaral.Military.WithdrawLoss = int.Parse(ret["withdraw_loss"].ToString());
				onegenaral.Military.WithdrawMorale = int.Parse(ret["withdraw_morale"].ToString());
				onegenaral.CityID = int.Parse(ret["owner_city_id"].ToString());
				return onegenaral;
			}
			catch (Exception ex)
			{
				return null; 
			}

		}


        /// <summary>
        /// Lấy thông tin về tướng, có thể lấy cả trong thành hoặc trại. Lấy được những gì thì ko rõ.
        /// </summary>
        /// <param name="cityid"></param>
        /// <param name="generalid"></param>
        /// <returns></returns>
        public static LVClient.Command.CityObj.MilitaryGeneral GetGeneralMilitaryInfoINCityNTrai(int cityid, int generalid)
        {
            try
            {
                LVClient.Command.CityObj.MilitaryGeneral gen = null;
               
                if (cityid > 0)		// thành
                    gen= Command.Common.GetGeneralMilitaryInfoEx(cityid, generalid);
                else  // trại
                    gen= Command.Common.GetGeneralInforInLuyenBinh(cityid, generalid);

                return gen;

            }
            catch (Exception ex)
            {
                return null;
            }
        }

		// lay ca thong tin ve Tan binh, sy khi .. trong bien che
		/// <summary>
		/// Lấy thông tin về tướng, bao gôm thông tin về quân số, vũ khí, sỹ khí, lương tân binh 
		/// </summary>
		/// <param name="cityid"></param>
		/// <param name="generalid"></param>
		/// <returns></returns>
		public static LVClient.Command.CityObj.MilitaryGeneral GetGeneralMilitaryInfoEx(int cityid, int generalid)
		{
			try
			{
				LVClient.Command.CityObj.MilitaryGeneral onegenaral = new LVClient.Command.CityObj.MilitaryGeneral();

				string para = "gid=16&pid=21&tab=2";
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

				Hashtable ret = Command.Build.SelectBuildingInfo(cityid, 16, 21, 2, cookies);


				if (ret == null) return null;

				onegenaral.Military.TanBinh = int.Parse((ret["trainee"].ToString()));
				onegenaral.GeneralId = generalid;
				onegenaral.CityID = cityid;
				ArrayList arGeneral = (ArrayList) ret["generals"];	
				ArrayList g;
				ArrayList bienche;
				for (int i =0; i < arGeneral.Count; i++)
				{
					g = (ArrayList) arGeneral[i];
					if (int.Parse(g[0].ToString()) == generalid )
					{
						onegenaral.Military.SoQuanCamDuoc = int.Parse(g[2].ToString());
						onegenaral.Military.SoQuanDangCo = int.Parse(g[3].ToString());
						onegenaral.Military.SyKhi = int.Parse(g[8].ToString());



						//ArrayList arTemp = ((ArrayList)ret["infantry_equip"]);
						bienche = (ArrayList)g[4];
						onegenaral.Military.Bobinh[0] = int.Parse(bienche[0].ToString());  // so luong bo binh hien co
						onegenaral.Military.Bobinh[1] = int.Parse(bienche[1].ToString());	// loai vu khi 1
						onegenaral.Military.Bobinh[2] = int.Parse(bienche[3].ToString());
						onegenaral.Military.Bobinh[3] = int.Parse(bienche[5].ToString());

						bienche = (ArrayList)g[5];
						onegenaral.Military.KyBinh[0] = int.Parse(bienche[0].ToString());   // so luong ky binh hien co
						onegenaral.Military.KyBinh[1] = int.Parse(bienche[1].ToString());	// loai vu khi 1
						onegenaral.Military.KyBinh[2] = int.Parse(bienche[3].ToString());
						onegenaral.Military.KyBinh[3] = int.Parse(bienche[5].ToString());

						bienche = (ArrayList)g[6];
						onegenaral.Military.CungThu[0] = int.Parse(bienche[0].ToString());   // so luong ky binh hien co
						onegenaral.Military.CungThu[1] = int.Parse(bienche[1].ToString());	// loai vu khi 1
						onegenaral.Military.CungThu[2] = int.Parse(bienche[3].ToString());
						onegenaral.Military.CungThu[3] = int.Parse(bienche[5].ToString());

						bienche = (ArrayList)g[7];
						onegenaral.Military.Xe[0] = int.Parse(bienche[2].ToString());   // so luong ky binh hien co
						onegenaral.Military.Xe[1] = int.Parse(bienche[0].ToString());	// loai vu khi 1
						//onegenaral.Military.Xe[2]int.Parse(arTemp[3]);
						//onegenaral.Military.Xe[3]int.Parse(arTemp[5];

						return onegenaral;
					}
				}
				return null;
			}
			catch (Exception ex)
			{
				return null;
			}

		}
        public static Hashtable GetGeneralInfo(int id) {
            string parameter = "";
            parameter += "lGeneralID=" + id;
            parameter += "&lCityID=" + 0;
            return Execute(14, parameter, true);
        }
        public static Hashtable GetAllSell() {
            string parameter = "";
            parameter += "stab=2";
            return Execute(38, parameter, true);
        }
        public static Hashtable GetMarketSeller(int typeres) {
            //type: 2 = gỗ, 1 = lúa , 3 = đá, 4 = sắt
            //mã lỗi > 0
            string parameter = "";
            parameter += "stab=1";
            parameter += "&tid=0";
            parameter += "&type=" + typeres;
            return Execute(38, parameter, true);
        }
        public static Hashtable GetMarketSeller(int typeres,string cookies) {
            //type: 2 = gỗ, 1 = lúa , 3 = đá, 4 = sắt
            //mã lỗi > 0
            string parameter = "";
            parameter += "stab=1";
            parameter += "&tid=0";
            parameter += "&type=" + typeres;
            return Execute(38, parameter, true, cookies);
        }

		// lay thong tin ve tuong trong binh truong/luyen binh (kha nang khong lay duoc trong thanh, khong biet tai sao
		public static LVClient.Command.CityObj.MilitaryGeneral[] GetGeneralInforInLuyenBinh(int cityid)
		{
			try
			{

				Hashtable ret = null;
				ArrayList list = null;
				//string para = "gid=16&pid=29&tab=6&tid=" + cityid;
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
				LVClient.Command.City.SwitchCitySlow(cityid);

				int citypost = LVClient.Command.City.GetCityPostByID(cityid);

				LVClient.Command.CityObj.Building building;

				int gid;
				int pid = -1;
				int tid;
				string para;
				ArrayList onegen;
				LVClient.Command.CityObj.MilitaryGeneral[] g =  null;
				
                if (cityid > 0)			// thanh
				{
                    gid = 16;
#if (DEBUG)                    
                    if (LVClient.Command.CityObj.City.AllCity[citypost].size == 4) gid = 69;
#endif                    
					
                    tid = 0;
				}
				else
				{
					gid = 19;
					tid = cityid;
				}


				if (LVClient.Command.CityObj.City.AllCity[citypost].AllBuilding == null)
					LVClient.Command.City.GetAllBuilding(citypost, false);

				for (int i = 0; i < LVClient.Command.CityObj.City.AllCity[citypost].AllBuilding.Length; i++)
				{
					if (gid == LVClient.Command.CityObj.City.AllCity[citypost].AllBuilding[i].gid)
					{
						pid = LVClient.Command.CityObj.City.AllCity[citypost].AllBuilding[i].pid;
						break;
					}

				}

				if (pid == -1) return null;
				

				if (cityid > 0)			// thanh
				{
	
					

					bool test = (Command.Build.SelectBuilding(cityid, 16, cookies));


					// select city
					//POST /GateWay/City.ashx?id=50&0.82967120251865&tid=-14042
					
					para = "tid=" + cityid;
					//ret = LVClient.Command.City.Execute(50, para, true);

					//POST http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=41&0.7000543635394991&lCityCampID=13139
					// selct city
					//para = "lCityCampID=" + cityid;
					//ret = LVClient.Command.Common.Execute(41, para, true);


					// select cac cong trinh
					//http://s3.linhvuong.zooz.vn/GateWay/City.ashx?id=5&0.6657390354561192&=
					//para = "";
					//ret = LVClient.Command.City.Execute(5, para, true, cookies);


					// selec binh truong
					//http://s3.linhvuong.zooz.vn/GateWay/Build.ashx?id=2&0.6491323077538449
					//pid=29&gid=16&tab=0&tid=0

					//para = "gid=" + gid + "&pid=" + pid + "&tab=0&tid=0";
					//ret = LVClient.Command.Build.Execute(2, para, true, cookies);


					//http://s3.linhvuong.zooz.vn/GateWay/Build.ashx?id=2&0.15782067665161664
					//pid=29&gid=16&tab=6&tid=0

					//para = "pid=" + pid + "&gid=" + gid + "&tab=6&tid="	 +tid;
					para = "gid=" + gid + "&pid=-1&tab=6&tid=" + tid;

				}
				else					// trai
				{	
					para = "gid=" + gid + "&pid=" + pid + "&tab=6&tid=" + tid;
				}

				ret = LVClient.Command.Build.Execute(2, para, true, cookies);
				if (ret == null) return null;
				list = (ArrayList)ret["list"];
				if (list == null) return null;
				if (list.Count <= 0) return null;

				g = new LVClient.Command.CityObj.MilitaryGeneral[list.Count];
				LVClient.Command.CityObj.MilitaryGeneral g2;
				for (int i = 0; i < list.Count; i++)
				{

					onegen = (ArrayList)list[i];
					g2 = new LVClient.Command.CityObj.MilitaryGeneral();

					g2.GeneralId = int.Parse(onegen[1].ToString());
					g2.GeneralName = onegen[2].ToString();
					g2.Military.Bobinh[0] = int.Parse(onegen[3].ToString());
					g2.Military.KyBinh[0] = int.Parse(onegen[4].ToString());
					g2.Military.CungThu[0] = int.Parse(onegen[5].ToString());
					g2.Military.Xe[0] = int.Parse(onegen[6].ToString());
					g2.Military.SyKhi = int.Parse(onegen[7].ToString());

					g[i] = g2;
				}
								 
				
				return g;
			}
			catch (Exception ex)
			{
				return null;
			}
		}

		public static LVClient.Command.CityObj.MilitaryGeneral GetGeneralInforInLuyenBinh(int cityid, int generalid)
		{
			LVClient.Command.CityObj.MilitaryGeneral[] g = GetGeneralInforInLuyenBinh(cityid);
			if (g == null) return null;

			foreach (LVClient.Command.CityObj.MilitaryGeneral g1 in g)
			{
				if (generalid == g1.GeneralId)
					return g1;
			}

			return null;
		}

		public static int GetGeneralSyKhiInLuyenBinh(int cityid, int generalid)
		{

			try
			{	
				return GetGeneralInforInLuyenBinh(cityid, generalid).Military.SyKhi;				
			}
			catch (Exception ex)
			{
				return -1;
			}
		}

		/*public static int GetGeneralSyKhiInLuyenBinh(int generalid, string cookies)
		{
			try
			{
				//string para = "gid=16&pid=29&tab=6&tid=" + cityid;
				string para = "gid=16&pid=29&tab=6&tid=0";
				//string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

				Hashtable ret = Execute(2, para, true, cookies);
				if (ret == null) return -1;

				ArrayList list = (ArrayList)ret["list"];
				ArrayList onegen;
				for (int i = 0; i < list.Count; i++)
				{
					onegen = (ArrayList)list[i];
					if (int.Parse(onegen[1].ToString()) == generalid)
						return int.Parse(onegen[7].ToString());
					
				}
				return -1;


			}
			catch (Exception ex)
			{
				return -1;
			}

		}
		 */ 



		// Laays thong tin ve tuong trong thanh/trai
        public static void GetGeneral(int citypos) 
		{
            Hashtable general = new Hashtable();
            string parameter = "";
            parameter += "ltype=4";
            parameter += "&tid=";
            general = Execute(15, parameter, true);
            try {
                ArrayList incity = (ArrayList)general["generals"];
                Command.CityObj.City.AllCity[citypos].MilitaryGeneral = new LVClient.Command.CityObj.MilitaryGeneral[incity.Count];
				ArrayList oneincity = null;
                int j = 0;
                for (int i = 0; i < incity.Count; i++) {
                    //ArrayList oneincity = (ArrayList)incity[i];
					oneincity = (ArrayList)incity[i];
                    
					if (oneincity[4].ToString()=="2") {
                        Command.CityObj.MilitaryGeneral g = new LVClient.Command.CityObj.MilitaryGeneral();
                        g.GeneralId = int.Parse(oneincity[0].ToString());
						g.GeneralName = (string)oneincity[1];
                        Command.CityObj.City.AllCity[citypos].MilitaryGeneral[j] = g;
                        j++;
                    }
                }
            } catch (Exception erx) {
                erx = null;
            }
        }

		// Laays thong tin ve tuong trong thanh/trai
		public static void GetGeneral(int citypos, bool reload)
		{
			lock (GeneralisLock)
			{
				int count = 0;

				if (!reload && Command.CityObj.City.AllCity[citypos].MilitaryGeneral != null) return;


				Hashtable general = new Hashtable();
				string parameter = "";
				parameter += "ltype=4";
				parameter += "&tid=";
				//general = Execute(15, parameter, true);

				int cityID = Command.CityObj.City.AllCity[citypos].id;
				//LVClient.Command.City.SwitchCitySlow(cityID);
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
				while (count < 10)
				{
					// lay danh sach quan van + quan vo
					general = Execute(15, parameter, true, cookies);
					if (general != null) break;

					count++;
					System.Threading.Thread.Sleep(1000);
				}
				try
				{
					ArrayList incity = (ArrayList)general["generals"];

					//Hungtv rem
					//Command.CityObj.City.AllCity[citypos].AllGeneral = new LVClient.Command.CityObj.General[incity.Count];

					ArrayList oneincity = null;
					ArrayList genList = new ArrayList();
					int j = 0;

					Command.CityObj.MilitaryGeneral g;
					for (int i = 0; i < incity.Count; i++)
					{
						//ArrayList oneincity = (ArrayList)incity[i];
						oneincity = (ArrayList)incity[i];

						if (oneincity[4].ToString() == "2")				//=2: quan vo; =1: quan van
						{
							g = new LVClient.Command.CityObj.MilitaryGeneral();
							g.GeneralId = int.Parse(oneincity[0].ToString());
							g.GeneralName = (string)oneincity[1];
							g.GeneralStatus = int.Parse(oneincity[5].ToString());
							genList.Add(g);
							//Command.CityObj.City.AllCity[citypos].AllGeneral[j] = g;

							j++;
						}
					}

					Command.CityObj.City.AllCity[citypos].MilitaryGeneral = new LVClient.Command.CityObj.MilitaryGeneral[genList.Count];
					for (int i = 0; i < genList.Count; i++)
					{
						Command.CityObj.City.AllCity[citypos].MilitaryGeneral[i] = (LVClient.Command.CityObj.MilitaryGeneral)genList[i];

					}
					int ii;
				}
				catch (Exception erx)
				{
					erx = null;
				}
			}
		}


		/// <summary>
		/// Update Simple General info in all city
		/// </summary>
		/// <param name="reload">true: sẽ update hết kể cả hiện tại đang có dữ liệu, false: chỉ update khi thành đó không có thôgn tin gì về tướng</param>
		public static void GetAllSimpleMilitaryGeneralInfoIntoCity()
		{

			Hashtable result = GetAllSimpleMilitaryGeneralInfo();

			if (result == null) return;

			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
			{
				//if (Command.CityObj.City.AllCity[i].MilitaryGeneral != null && !reload) continue;

				Command.CityObj.City.AllCity[i].MilitaryGeneral = 
					(LVClient.Command.CityObj.MilitaryGeneral[]) result[Command.CityObj.City.AllCity[i].id];

			}
		}


		/// <summary>
		/// Lấy thông tin cơ bản về tướng như cấp, level, sức mạnh, thống lĩnh ... ở phần nội chính
		/// </summary>
		/// <param name="cityid">cityid cuar thành cần lấy tướng</param>
		/// <returns>LVClient.Command.CityObj.MilitaryGeneral[]: chỉ bao gồm tên, id, thành, thể lực, sức mạnh, level...  </returns>
		public static LVClient.Command.CityObj.MilitaryGeneral[] GetAllSimpleMilitaryGeneralInfo(int cityid)
		{
			try
			{

				Hashtable result = GetAllSimpleMilitaryGeneralInfo();
				if (result == null || result.Count == 0) return null;

				return (LVClient.Command.CityObj.MilitaryGeneral[])result[cityid];
			}
			catch (Exception ex)
			{
				return null;
			}
		}

		/// <summary>
		/// Lấy thông tin cơ bản về quan văn như cấp, level, sức mạnh, thống lĩnh ... ở phần nội chính/nhân sự
		/// </summary>
		/// <returns>Hastable object. Key: cityID, Value: LVClient.Command.CityObj.CivilGeneral[] </returns>
		public static Hashtable GetAllSimpleCivilGeneralInfo()
		{
			try
			{
				LVClient.Command.CityObj.CivilGeneral[] miligen = null;

				//http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=32&0.2614652350805371&type=1

				Hashtable result = LVClient.Command.Common.Execute(32, "type=1", true);

				if (result == null || result["ret"].ToString() != "0") return null;
				ArrayList list = (ArrayList)result["list"];

				// quan văn
				// http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=32&0.1458047635938451&type=1
				//{"ret":0,"list":[[10718,"iwunu7(Đô thành)",255,-231,[[407419,"Lộ An Trực","",1,0,0,29,100,390,390,35,54,29,290,0],
				//[298308,"MS-VietCat","",1,3,0,172,100,1820,1820,221,140,215,1720,0],[390593,"Tư Phong Hòa","",1,0,0,51,100,610,610,38,29,14,510,0],
				//[390594,"Vân Nam Tú","",1,0,0,24,100,340,340,62,57,51,240,0],[390595,"Nghiêm Triển Bá","",1,0,0,45,100,550,550,47,57,59,450,0],[390596,"Nhược Đồng","",1,0,0,17,100,270,270,26,42,50,170,0],[390597,"Long Hải Đạo","",1,0,0,43,100,530,530,80,45,63,430,0],[390598,"Trần Đấu Diêu","",1,0,0,28,100,380,380,22,63,27,280,0],[390600,"Ấn Dục Ao","",1,0,0,37,100,470,470,32,46,10,370,0],[390601,"Lương Công","",1,0,0,31,100,410,410,23,45,70,310,0],[390602,"Bạo Nghĩa","",1,0,0,51,100,610,610,84,72,69,510,0],[390603,"Vạn Hầu Niên","",1,0,0,31,100,410,410,51,44,10,310,0],[390604,"Cung Diệp Cốc","",1,0,0,31,100,410,410,35,73,32,310,0],[390605,"Cốc Bá Niên","",1,0,0,23,100,330,330,31,28,62,230,0],[390606,"Đông Phương Đẳng Kiện","",1,0,0,44,100,540,540,77,71,84,440,0],[390607,"Ba Hoài Kiếm","",1,0,0,23,97,330,330,14,25,19,230,0],[390608,"Phương Thơ Viên","",1,0,0,32,100,420,420,38,39,68,320,0],[390609,"Điền Chiến Phú","",1,0,0,53,100,630,630,29,36,23,530,0],[390611,"Kim Trình Hạo","",1,0,0,23,100,330,330,30,44,38,230,0],[390612,"Đông Phương Bạc Dịch","",1,0,0,32,100,420,420,51,42,54,320,0],[390613,"Ô Bá Đồ","",1,0,0,22,100,320,320,50,13,34,220,0],[390614,"Công Dương Ải Sơn","",1,0,0,11,100,210,210,41,52,10,110,0],[390615,"Chu Bảo Ao","",1,0,0,10,100,200,200,18,20,35,100,0],[390616,"Lục Mỹ Ao","",1,0,0,148,97,1580,1580,190,28,210,1480,8],[367251,"Quách Nguyên","",1,0,0,39,100,490,490,40,29,47,390,90],[357046,"Thái Phẩm","",1,0,0,50,97,600,600,63,91,83,500,0],[356067,"Tào Tục Thụ","",1,1,0,236,100,2460,2460,310,73,370,2360,6],[316126,"Gia Cát Cẩn*","Gia Cát Cẩn",1,3,16,287,100,3450,3450,800,810,90,2870,4],[247826,"Thi Ao","",1,0,0,51,100,610,610,15,64,81,510,0],[218280,"Lý Khôi","Lý Khôi",1,2,0,243,100,2660,2660,620,610,85,2430,2]]],[-42662,"7.1",13,-97,[[356066,"Hạ Bá Kiên","",1,2,0,146,100,1560,1560,230,60,170,1460,1],[116866,"Ms-Nga ha","",1,0,0,172,100,1820,1820,221,271,66,1720,5]]],[-42670,"7.2",33,-102,[[289999,"TT 11","",1,2,0,215,100,2250,2250,266,66,331,2150,3],[282676,"Hành Thất Hạo","",1,0,0,1,97,110,110,12,13,14,10,0]]],[13139,"iwunu5",265,-229,[[305302,"Em nhường các anh","Từ Thứ",1,3,24,305,100,3890,3890,870,890,70,3050,10],[426325,"Đổng Diêu Tuyền","",1,0,0,33,100,430,430,50,71,41,330,6],[426327,"Thái Hậu Mục","",1,0,0,56,100,660,660,16,71,89,560,0],[426328,"Cốc Đơn Kiếm","",1,0,0,36,100,460,460,49,72,29,360,0],[426329,"Hoành Phù Viên","",1,0,0,43,100,530,530,78,52,17,430,0],[426331,"Tấn Dịch","",1,0,0,17,100,270,270,20,47,55,170,0],[426333,"Hoàn Kị Hương","",1,0,0,20,100,300,300,12,52,19,200,0],[426334,"Thi An Hưng","",1,0,0,52,100,620,620,48,24,84,520,0],[426336,"Tiền Cốc Đồ","",1,0,0,11,100,210,210,31,16,34,110,0],[367262,"Nguyễn Đông Phục","",1,0,0,15,100,250,250,15,36,55,150,0],[363879,"Hoài Bối","",1,0,0,4,100,140,140,16,16,21,40,0],[363880,"Ngô Phục Thạc","",1,0,0,29,100,390,390,62,62,40,290,0],[355643,"Bùi Chấn Đắc","",1,0,0,21,100,310,310,45,14,52,210,0],[282212,"*Khổng Dung","Khổng Dung",1,3,0,262,100,2980,2980,740,710,90,2620,2],[284331,"Phùng Kỉ","Phùng Kỉ",1,2,0,273,100,3110,3110,720,730,102,2730,8],[265850,"xxx","",1,0,0,181,100,1910,1910,221,45,258,1810,0],[261277,"2","",1,3,0,170,97,1800,1800,181,261,89,1700,6],[166105,"Lưu Kỳ","Lưu Kỳ",1,1,0,238,100,2500,2500,260,385,450,2380,9],[130935,"Ms","",1,0,0,198,100,2080,2080,235,82,260,1980,0]]],[-46538,"5.1",261,-228,[[367259,"Nghiêm Mộc An","",1,2,0,120,100,1300,1300,131,120,47,1200,6]]],[-22800,"5.2",-4,-83,[[290000,"Đông Dịch Nhã","",1,3,0,53,100,630,630,37,32,46,530,0],[247827,"Phán Cách Quang","",1,0,0,46,100,560,560,70,70,60,460,0],[237965,"Thọ Diệc","",1,0,0,47,100,570,570,32,17,16,470,0],[136658,"Tào Công","",1,0,0,74,100,840,840,75,84,101,740,24],[130951,"MS-Mo Dung","",1,2,0,118,100,1280,1280,143,174,40,1180,0]]],[-16702,"5.3",14,-93,[[80065,"Ms-Lữ Tường","",1,2,0,180,100,1900,1900,270,170,110,1800,7]]],[-14042,"5.4",262,-227,[[355642,"Lương Qúy Trạch","",1,0,0,32,100,420,420,12,44,61,320,0],[247828,"Chi Cung Bang","",1,0,0,43,100,530,530,21,68,29,430,0],[123502,"Hữu Thanh","",1,2,0,154,100,1640,1640,130,200,88,1540,3],[88212,"Ms-","",1,0,0,110,100,1200,1200,152,147,50,1100,4]]],[13835,"iwunu19(Đô Thành)",259,-235,[[426279,"Tư Đồ Bột Ban","",1,0,0,40,100,500,500,26,36,55,400,0],[426280,"Quan Cô Định","",1,0,0,35,97,450,450,61,12,73,350,6],[426281,"Khả Quảng Thành","",1,0,0,36,100,460,460,57,71,33,360,0],[426282,"Hoa Hùng Lực","",1,0,0,62,100,720,720,45,59,18,620,0],[426283,"Cổ Thảo","",1,0,0,33,100,430,430,61,23,50,330,0],[426284,"Lâm Lục Nam","",1,0,0,41,100,510,510,11,28,47,410,0],[426285,"Cường Trạch Trụ","",1,0,0,36,100,460,460,45,41,37,360,0],[426286,"Mạnh Hiền Huy","",1,0,0,30,97,400,400,39,38,40,300,0],[426287,"Hầu Bố Lan","",1,0,0,44,100,540,540,21,57,13,440,0],[426288,"Hoài Lộ Khai","",1,0,0,50,100,600,600,27,13,86,500,0],[426289,"Vạn Cốc Ao","",1,0,0,17,100,270,270,48,40,31,170,0],[426290,"Trạng Kim Thơ","",1,0,0,23,100,330,330,52,32,19,230,0],[426291,"Gia Văn Khang","",1,0,0,33,100,430,430,74,70,16,330,0],[426292,"Mộ Dung Niên Huy","",1,0,0,39,100,490,490,26,36,67,390,0],[426293,"Hồng Đinh Kiện","",1,0,0,36,97,460,460,11,40,74,360,0],[426294,"Lục Lạc Hiền","",1,0,0,39,100,490,490,27,83,45,390,0],[426295,"Lô Thạch","",1,0,0,29,100,390,390,42,25,62,290,0],[426296,"Lão Định","",1,0,0,16,100,260,260,42,25,56,160,0],[426297,"Lam Viên Bá","",1,0,0,52,100,620,620,74,35,88,520,0],[426298,"Ưng Đồ Kiệm","",1,0,0,33,97,430,430,60,52,51,330,0],[426299,"Mai Cung Túc","",1,0,0,61,100,710,710,102,17,25,610,0],[426300,"Hoằng Trực","",1,0,0,10,100,200,200,42,48,39,100,0],[426301,"Thi Nghĩa Vĩ","",1,0,0,13,97,230,230,21,57,37,130,0],[426302,"Huỳnh Kì An","",1,0,0,15,100,250,250,19,51,15,150,0],[378005,"Vệ Đồng","",1,2,0,57,100,670,670,65,80,72,570,0],[356224,"Võ Định Dị","",1,1,0,228,100,2380,2380,310,40,350,2280,5],[116869,"Ms-22","",1,3,0,170,97,1800,1800,230,231,18,1700,0],[114607,"MS-*Tổ Lang","",1,3,0,167,100,1770,1770,230,261,69,1670,3],[16025,"Hoàn Cách Nhạn","",1,0,0,132,100,1420,1420,200,18,200,1320,0]]],[-46763,"19.1",-14,-77,[[407366,"Hoàn Định Đạo","",1,2,0,2,100,120,120,13,10,17,20,0]]],[-44431,"19.2",26,-98,[[21708,"TT iwunu3","",1,2,0,224,100,2340,2340,324,32,345,2240,0]]],[17485,"iwunu12(Đô Thành)",265,-247,[[409472,"Sử Bối Côn","",1,0,0,10,100,200,200,27,39,20,100,0],[409473,"La Kiện Thúy","",1,0,0,6,100,160,160,38,37,33,60,0],[409474,"Hòa Nguyên","",1,0,0,31,100,410,410,25,23,57,310,0],[409475,"Phàn Dị Văn","",1,0,0,16,100,260,260,22,44,19,160,0],[409476,"Hoằng Hứa Định","",1,0,0,22,100,320,320,23,19,28,220,0],[409477,"Vu Trạch","",1,0,0,21,100,310,310,41,25,19,210,0],[409478,"Long Tuyệt Diệc","",1,0,0,26,100,360,360,47,45,47,260,0],[409479,"Quân Cách Trùng","",1,0,0,9,97,190,190,35,17,18,90,0],[409483,"Mộ Dung Cốc","",1,0,0,17,100,270,270,17,22,10,170,0],[409484,"Viên Hiệp","",1,0,0,37,100,470,470,22,17,29,370,0],[409486,"Không Minh Phong","",1,0,0,35,100,450,450,53,58,27,350,0],[409487,"Kim CamCác","",1,0,0,36,100,460,460,35,50,14,360,0],[237964,"3","",1,2,0,129,100,1390,1390,76,127,114,1290,0],[76468,"*Tôn Lượng","Tôn Lượng",1,1,0,254,100,2690,2690,421,305,420,2540,5]]],[19357,"iwunu10(Đô Thành)",254,-227,[[355640,"Tư Mã Nam","",1,3,0,46,100,560,560,41,36,65,460,0],[407418,"Cốc Xuân Diệp","",1,3,0,27,100,370,370,39,23,21,270,0],[407421,"Du Hồng Khải","",1,0,0,2,100,120,120,27,27,27,20,0],[407423,"Cát Hiệp Nhẫn","",1,0,0,6,100,160,160,15,34,14,60,0],[407424,"Tổ Kiếm Phương","",1,0,0,20,100,300,300,25,28,31,200,0],[407425,"Tống Văn","",1,0,0,2,97,120,120,17,14,18,20,0],[407426,"Hầu Hi Túc","",1,0,0,12,100,220,220,41,35,33,120,0],[407427,"Ngư Luân Kiều","",1,0,0,15,100,250,250,37,44,44,150,0],[407428,"Ba Biên","",1,0,0,2,100,120,120,24,24,30,20,0],[407429,"Tiền Văn Xuân","",1,0,0,18,97,280,280,32,10,35,180,0],[407430,"Mộ Dung Ngũ","",1,0,0,32,100,420,420,27,25,15,320,0],[407431,"Đổng Huy Nhã","",1,0,0,3,97,130,130,17,20,31,30,0],[407432,"Âm Trực Đơn","",1,0,0,18,100,280,280,21,19,23,180,0],[407433,"Lam Nhiếp","",1,0,0,33,100,430,430,36,17,53,330,0],[407434,"Vạn Bá","",1,0,0,9,100,190,190,37,28,14,90,0],[407435,"Xương Dạ Tuyền","",1,0,0,22,100,320,320,48,23,41,220,0],[407436,"Lý Hạo Chấn","",1,0,0,17,100,270,270,36,20,17,170,0],[282680,"Lam Tây","",1,0,0,28,100,380,380,42,56,57,280,0],[209084,"Vấn Bạch","",1,1,0,238,100,2480,2480,330,30,360,2380,2]]],[20118,"iwunu11(Đô Thành)",265,-219,[[478574,"Thọ Thảo","",1,0,0,15,100,250,250,13,37,13,150,0],[478573,"Cường Lượng Quang","",1,0,0,20,100,300,300,36,39,64,200,0],[478572,"Vân Minh Phúc","",1,0,0,21,100,310,310,31,22,25,210,0],[478571,"Thi Luân Hạo","",1,0,0,17,100,270,270,57,38,17,170,0],[478570,"Hà Đức Đạo","",1,0,0,59,100,690,690,56,82,50,590,0],[478569,"Mai Diệc Huy","",1,0,0,10,100,200,200,45,22,46,100,0],[478568,"Thành Biên Bang","",1,0,0,31,100,410,410,42,35,43,310,0],[478567,"Tôn Hải Nhiếp","",1,0,0,47,100,570,570,91,89,74,470,0],[478566,"Công Tôn Bá Túc","",1,0,0,48,100,580,580,47,46,41,480,0],[478565,"Quảng Bá Ban","",1,0,0,59,100,690,690,48,33,30,590,0],[478564,"Công Tường","",1,0,0,64,100,740,740,93,41,107,640,0],[478563,"Mục Đẳng Đơn","",1,0,0,13,100,230,230,43,57,24,130,0],[478562,"Tương Kiếm","",1,0,0,56,100,660,660,10,76,66,560,0],[478561,"Hạ Hầu Hi Vũ","",1,0,0,26,100,360,360,58,70,47,260,0],[478560,"Chương Chiến Trạch","",1,0,0,28,97,380,380,22,24,49,280,0],[478559,"Đổng Trọng Hùng","",1,0,0,56,100,660,660,12,66,12,560,0],[478558,"Mạnh Trọng Thiên","",1,0,0,53,97,630,630,80,11,85,530,0],[478557,"Thiên Ức","",1,0,0,39,100,490,490,49,38,51,390,0],[478556,"Trạng Diệc Quang","",1,0,0,39,100,490,490,22,16,79,390,0],[478555,"Trung Khánh Thạch","",1,0,0,18,100,280,280,60,31,52,180,0],[478554,"Toàn Kiều Văn","",1,0,0,34,100,440,440,56,17,33,340,0],[478553," Chính Công An","",1,0,0,24,100,340,340,59,18,11,240,0],[478552,"Tiêu Hiệp Sơn","",1,0,0,21,100,310,310,55,51,36,210,0],[478551,"Dung Quế","",1,0,0,60,100,700,700,94,67,26,600,0],[478550,"Diệp Công","",1,0,0,42,100,520,520,64,62,81,420,0],[478549,"Mã Ninh Hứa","",1,0,0,51,97,610,610,62,66,91,510,0],[478548,"Hành Xuân","",1,0,0,40,100,500,500,50,34,19,400,0],[478547,"Âu Trung Long","",1,0,0,55,100,650,650,69,55,99,550,0],[478546,"Thọ Lưu","",1,0,0,49,100,590,590,42,86,87,490,0],[478545,"Không Quy Hi","",1,0,0,63,100,730,730,13,67,70,630,0],[406975,"Hiên Viên Hưng Đông","",1,2,0,49,97,590,590,15,65,70,490,0],[406976,"Tòng Thụ Dục","",1,0,0,23,100,330,330,21,29,25,230,0],[170129,"Trần Kiều-MsĐộtCốt","Trần Kiều",1,1,0,233,100,2430,2430,291,390,400,2330,5]]],[22604,"iwunu1(Đô Thành)",261,-230,[[237963,"Cao Công Cảnh","",1,1,0,214,100,2240,2240,300,21,310,2140,0],[209627,"Tào Thực-msQHoi","Tào Thực",1,2,0,223,100,2420,2420,561,460,221,2230,8]]],[22881,"iwunu20(Đô Thành)",279,-255,[[437461,"Song Ao Dị","",1,0,0,43,100,530,530,50,11,53,430,0],[437462,"Bạch Huyên Công","",1,0,0,57,100,670,670,48,51,84,570,0],[437463,"Hán Đông Ban","",1,0,0,47,100,570,570,29,21,23,470,0],[437464,"Bành Linh Kiếm","",1,0,0,37,100,470,470,51,11,73,370,0],[437465,"Mộ Dung Lan","",1,0,0,34,100,440,440,12,48,37,340,0],[437466,"Mộng Lực Linh","",1,0,0,52,100,620,620,94,39,35,520,0],[437467,"Ưng Xuyên Hải","",1,0,0,51,100,610,610,79,12,69,510,0],[437468,"Khúc Thơ","",1,0,0,48,100,580,580,49,21,29,480,0],[437470,"Mạnh Văn Bá","",1,0,0,53,100,630,630,63,65,67,530,0],[437471,"Vân Luân Diệp","",1,0,0,58,100,680,680,38,57,20,580,0],[437472,"Nhan Khải Quang","",1,0,0,33,100,430,430,65,15,45,330,0],[437473,"Lâm Vĩ","",1,0,0,20,100,300,300,11,45,48,200,0],[437475,"Thành Phi","",1,0,0,58,97,680,680,37,37,36,580,0],[437477,"Tùng Khang","",1,0,0,32,100,420,420,46,70,53,320,0],[437479,"Vạn Nghiêm","",1,0,0,46,100,560,560,13,36,44,460,0],[437481,"Diệp Hoài","",1,0,0,42,100,520,520,20,12,52,420,0],[437483,"Toàn Nhẫn","",1,0,0,45,97,550,550,37,73,11,450,0],[437484,"Trần Khánh","",1,0,0,35,100,450,450,57,64,41,350,0],[437594,"Diêu Sơn","",1,0,0,13,100,230,230,55,46,34,130,0],[437595,"La Hào Bưu","",1,0,0,38,100,480,480,60,18,56,380,0],[437596,"Lộ Biểu Diệc","",1,0,0,25,100,350,350,39,58,30,250,0],[437597,"Tòng Không Tổng","",1,0,0,32,100,420,420,56,72,55,320,0],[437598,"Tịnh Du Nhẫn","",1,0,0,46,100,560,560,54,21,66,460,0],[406984,"Giang Cần","",1,2,0,53,100,630,630,23,89,65,530,0],[406986,"Đặng Minh","",1,0,0,40,100,500,500,68,47,38,400,0],[406987,"Không Nguyên","",1,0,0,23,100,330,330,58,11,16,230,0],[406988,"Cường Cần Bạc","",1,0,0,31,100,410,410,16,70,62,310,0],[406989,"Bình Hoàn Chiêu","",1,0,0,23,97,330,330,58,15,15,230,0],[406990,"Âm An Huy","",1,0,0,34,100,440,440,12,46,43,340,0],[376878,"Vệ Đức Tấn","",1,1,0,239,97,2490,2490,320,65,380,2390,9]]],[23381,"iwunu2(Đô Thành)",268,-247,[[48329,"Đỗ Tây Binh","",1,0,0,7,100,170,170,22,22,20,70,0],[20330,"TT Iwunu2","",1,1,0,248,97,2580,2580,360,44,391,2480,12],[22136,"Hoằng Hinh Văn","",1,0,0,1,100,110,110,12,11,13,10,0]]],[-6265,"2. Thuc 4x4",-1,-84,[[34235,"Hoa Mai Lộ","",1,2,0,5,100,150,150,16,12,13,50,0]]],[-4473,"2 Sat 3x3",-6,-81,[[22641,"Tổ La Hoàng","",1,2,0,1,100,110,110,15,14,13,10,0]]],[28200,"iwunu13(Đô Thành)",270,-264,[[437493,"Thành Mộc","",1,0,0,46,100,560,560,39,10,16,460,0],[437494,"Hành Túc","",1,0,0,24,100,340,340,42,42,50,240,0],[437495,"Tòng Lâm","",1,0,0,33,100,430,430,40,22,40,330,0],[437496,"Đặng Hồng Hứa","",1,0,0,37,100,470,470,23,47,46,370,0],[437497,"Ngô Thanh Hậu","",1,0,0,31,100,410,410,38,20,28,310,0],[437498,"Tề Trọng Đơn","",1,0,0,58,100,680,680,38,97,82,580,0],[437500,"Gia Cát Vũ Lộ","",1,0,0,57,97,670,670,63,66,70,570,0],[437501,"Vệ Kị Mạo","",1,0,0,23,100,330,330,31,53,29,230,0],[437502,"Từ Kiệm","",1,0,0,32,100,420,420,66,23,25,320,0],[437503,"Thành Hoài","",1,0,0,44,100,540,540,21,18,25,440,0],[437504,"Quốc Thảo","",1,0,0,26,100,360,360,60,59,23,260,0],[437505,"Cường Hậu Tạng","",1,0,0,10,100,200,200,46,17,50,100,0],[437506,"Trạng Uy Phong","",1,0,0,11,100,210,210,24,22,40,110,0],[437508,"Hiên Viên Trực","",1,0,0,28,100,380,380,33,10,18,280,0],[437509,"Hoành Trạch Viên","",1,0,0,33,100,430,430,67,66,65,330,0],[437511,"Lăng Mai Cung","",1,0,0,40,100,500,500,66,81,14,400,0],[437513,"Xương Nhã Đông","",1,0,0,38,100,480,480,44,69,30,380,0],[437515,"Nguyên Đinh Dư","",1,0,0,39,100,490,490,75,22,10,390,0],[437517,"Tư Đồ Trực","",1,0,0,50,100,600,600,55,39,21,500,0],[437518,"La Hưng","",1,0,0,52,100,620,620,51,57,22,520,0],[437519,"Bạch Quang Quảng","",1,0,0,51,100,610,610,19,23,87,510,0],[437520,"Ba CamCác","",1,0,0,19,100,290,290,18,16,27,190,0],[437521,"Ngô Trung Đồng","",1,0,0,40,100,500,500,53,21,73,400,0],[437522,"Chiến Viên Tổng","",1,0,0,11,100,210,210,50,17,35,110,0],[437523,"Tư Đồ Đắc Vân","",1,0,0,26,100,360,360,19,31,54,260,0],[437524,"Na Mỹ","",1,0,0,41,100,510,510,64,44,82,410,0],[437525,"Dương Thiêm Phi","",1,0,0,28,100,380,380,34,16,60,280,0],[407010,"Nhạc Diêu Thơ","",1,2,0,36,100,460,460,10,63,33,360,0],[282678,"Thám Linh Kiều","",1,1,0,245,100,2550,2550,340,32,360,2450,12]]],[34254,"iwunu3(Đô Thành)",268,-244,[[127065,"Ấn Tích","",1,2,0,36,100,460,460,44,54,29,360,0],[42182,"Hoàng Hạo","Hoàng Hạo",1,1,0,250,100,2590,2590,400,144,520,2500,20]]],[39557,"iwunu14(Đô Thành)",294,-265,[[428980,"*Tiểu Kiều","Tiểu Kiều",1,2,0,184,100,2220,2220,450,540,208,1840,1],[347019,"Âu Uy Ban","",1,0,0,215,100,2250,2250,271,85,340,2150,8],[434168,"Dương Tu*","Dương Tu",1,3,16,250,100,2980,2980,600,690,230,2500,5],[469092,"Na Tiêu Hi","",1,0,0,42,97,520,520,82,73,80,420,0],[469093,"Nhược Biểu Hùng","",1,0,0,45,100,550,550,81,55,38,450,0],[407368,"Hạ Hầu Biên Thất","",1,0,0,27,100,370,370,62,34,25,270,0],[407369,"Bạch Hiên","",1,0,0,63,100,730,730,50,34,71,630,0],[407370,"Vũ An Trung","",1,0,0,20,100,300,300,10,59,58,200,0],[407371,"Du Túc","",1,0,0,45,100,550,550,43,36,17,450,0],[407372,"Hoàn Văn","",1,0,0,29,100,390,390,45,45,53,290,0],[407373,"Phong Luân Mỹ","",1,0,0,34,97,440,440,72,47,50,340,0],[407374,"Diêu An Cô","",1,0,0,43,100,530,530,13,86,16,430,0],[407375,"Mộ Dung Luân","",1,0,0,34,100,440,440,52,12,52,340,0],[407377,"Hà Hi Quán","",1,0,0,26,100,360,360,44,62,42,260,0],[407379,"Dịch Luân Thịnh","",1,0,0,39,100,490,490,83,77,20,390,0],[407380,"Trử Thịnh","",1,0,0,20,100,300,300,37,10,21,200,0],[407381,"Trử Nhạn Ngũ","",1,0,0,16,100,260,260,39,22,45,160,0],[407382,"Tiền Đẳng Tây","",1,0,0,53,100,630,630,66,85,78,530,0],[407383,"Tặc Việt","",1,0,0,14,100,240,240,43,58,12,140,0],[407384,"Thần Kiện","",1,0,0,5,100,150,150,46,16,19,50,0],[407385,"Na Bố Cung","",1,0,0,53,97,630,630,15,83,26,530,0],[407386,"Sử Pháp","",1,0,0,54,100,640,640,48,45,96,540,0],[407387,"Lăng Hứa","",1,0,0,52,100,620,620,31,57,37,520,0],[407388,"Chu Quy","",1,0,0,13,100,230,230,17,40,22,130,0],[407389,"Khương Khánh","",1,0,0,22,100,320,320,14,26,34,220,0],[407390,"Ngư Phẩm Chấn","",1,0,0,21,100,310,310,14,49,27,210,0],[407391,"Khổng Việt Lạc","",1,0,0,36,100,460,460,19,60,28,360,0],[407392,"Vi Trung Thạch","",1,0,0,92,100,1020,1020,33,69,99,920,102],[407393,"Hành Qúy","",1,0,0,49,100,590,590,83,40,79,490,0],[407394,"Phán Khải","",1,0,0,11,100,210,210,35,38,25,110,0],[407395," Chính Khánh Bối","",1,0,0,26,100,360,360,12,37,27,260,0],[407396,"Vu Hậu","",1,0,0,54,97,640,640,58,33,52,540,0],[305410,"Xa Bích Bối","",1,1,0,250,100,2600,2600,321,35,350,2500,4]]],[40539,"iwunu4(Đô Thành)",258,-231,[[400187,"Khuông Phi Hoài","",1,0,0,56,100,660,660,24,21,50,560,0],[400188,"Cung Hoàn Ngũ","",1,0,0,47,100,570,570,60,22,73,470,0],[400192,"Diêu Nhẫn","",1,0,0,31,97,410,410,34,14,48,310,0],[400193,"Trử Không","",1,0,0,42,100,520,520,30,59,57,420,0],[400194,"Triều Vũ Mạo","",1,0,0,54,100,640,640,37,63,40,540,0],[400195,"Quảng TĩnhHảo","",1,0,0,41,97,510,510,37,48,27,410,0],[400196,"Tổ Bưu","",1,0,0,42,100,520,520,54,16,72,420,0],[400197,"Tần Thất Kiên","",1,0,0,59,100,690,690,67,77,44,590,0],[400198,"Mễ Trình Hiên","",1,0,0,32,100,420,420,47,50,56,320,0],[400199,"Kiều Văn Trung","",1,0,0,39,100,490,490,19,13,60,390,0],[400200,"Quan Đoan Bạch","",1,0,0,59,100,690,690,48,57,74,590,0],[400201,"Vạn Hầu Tường Phúc","",1,0,0,37,100,470,470,29,78,58,370,0],[400202,"Khổng Hòa Hạnh","",1,0,0,48,100,580,580,90,78,82,480,0],[400203,"Nhan Trung Chấn","",1,0,0,46,100,560,560,71,48,20,460,0],[400205,"Thủy Bạc Thụ","",1,0,0,38,100,480,480,78,42,48,380,0],[400206,"Tề Nguyên","",1,0,0,21,97,310,310,21,34,10,210,0],[400207,"Công Dương Bích","",1,0,0,28,100,380,380,38,70,10,280,0],[369749,"Chúc Vũ An","",1,0,0,28,100,380,380,45,29,21,280,0],[369750,"Tiêu Lam Kiện","",1,0,0,21,100,310,310,57,44,14,210,0],[355638,"Lục Tường","",1,0,0,4,100,140,140,37,27,32,40,0],[355641,"Lộ Tục An","",1,0,0,33,100,430,430,43,73,65,330,0],[307973,"Vấn Phúc Lực","",1,1,0,216,97,2260,2260,240,70,300,2160,5],[289998,"Ms-Ly Cat","",1,3,0,162,97,1720,1720,200,210,49,1620,1],[274577,"Tư Mã Ngũ Nê","",1,0,0,108,100,1180,1180,150,16,150,1080,0],[274578,"Hoành Lương Yến","",1,0,0,104,100,1140,1140,130,135,37,1040,3],[209085,"Ngư Nghiêm Đạo","",1,0,0,15,100,250,250,29,17,35,150,0],[134649,"Khổng Linh Sơn","",1,0,0,108,100,1180,1180,118,138,22,1080,24],[96511,"Ms-Đạp Đốn","",1,2,0,142,100,1520,1520,180,200,67,1420,2],[2280,"Liêm Trụ(Thai Thu)","",1,0,0,234,100,2440,2440,314,53,365,2340,3]]],[-46773,"4.1",-179,11,[[407438,"Lâm Bột","",1,2,0,78,97,880,880,100,90,32,780,7]]],[-42517,"4.2",28,-99,[[354211,"Cường Hạnh Côn","",1,0,0,44,100,540,540,40,23,18,440,0],[80062,"TT T7","",1,2,0,215,100,2250,2250,169,159,321,2150,9]]],[46999,"iwunu17(Đô Thành)",273,-260,[[407328,"Đường Dị","",1,2,0,31,100,410,410,55,54,15,310,0],[407331,"Diệp Lâm","",1,0,0,25,100,350,350,29,27,17,250,0],[407332,"Cát Thành Chiêu","",1,0,0,17,100,270,270,36,12,14,170,0],[407333,"Hà Bạc Thực","",1,0,0,18,100,280,280,16,28,36,180,0],[407334,"Không Hải Đắc","",1,0,0,10,100,200,200,35,36,20,100,0],[407335,"Liêm Phú","",1,0,0,11,100,210,210,17,14,16,110,0],[348409,"Không Hảo","",1,1,0,252,97,2620,2620,361,21,380,2520,7]]],[75587,"iwunu6(Đô Thành)",264,-238,[[240976,"Tấn Tú","",1,2,0,5,100,150,150,14,14,19,50,0],[68824,"5-Thai thu TL","",1,1,0,245,100,2550,2550,253,135,390,2450,9]]],[83080,"iwunu8(Đô Thành)",265,-253,[[407398,"Tông Lam Hiền","",1,0,0,5,100,150,150,20,16,18,50,0],[274267,"tt","",1,1,0,248,100,2580,2580,290,56,341,2480,6]]],[83365,"iwunu9(Đô Thành)",252,-224,[[410570,"Chu Trình","",1,0,0,4,100,140,140,10,11,14,40,0],[407362,"Huỳnh Vũ Mạn","",1,0,0,2,100,120,120,14,11,13,20,0],[407363,"Hoàng Đinh Hạnh","",1,2,0,6,100,160,160,18,15,17,60,0],[86525,"Ms-Hình Đạo Vinh","",1,1,0,250,100,2600,2600,210,191,390,2500,10]]],[93917,"iwunu15(Đô Thành)",256,-239,[[340490,"Hòa Trạch Bạc","",1,2,0,197,100,2070,2070,270,41,311,1970,6],[228528,"Đặng Ngải","Đặng Ngải",1,1,0,285,100,3760,3760,800,820,57,2850,55]]],[93938,"iwunu16(Đô Thành)",264,-250,[[408007,"Khúc Bá","",1,0,0,7,100,170,170,12,30,32,70,0],[408008,"Vân Xuân","",1,0,0,27,100,370,370,53,12,54,270,0],[408009,"Chiến Bá Hải","",1,0,0,16,100,260,260,37,42,35,160,0],[408010,"Mộng Hiệp Lưu","",1,0,0,29,100,390,390,11,13,50,290,0],[408011,"Bàng Chiến Đan","",1,0,0,3,100,130,130,22,17,12,30,0],[408012,"Đường Nghĩa Khánh","",1,0,0,9,100,190,190,34,36,14,90,0],[408013,"Phùng Sơn Tổng","",1,0,0,2,100,120,120,11,26,25,20,0],[408014,"Âm Triển","",1,0,0,29,100,390,390,32,54,30,290,0],[408015,"Viên Cần Định","",1,0,0,2,97,120,120,19,11,13,20,0],[408016,"Tiêu Trình Đan","",1,0,0,24,100,340,340,28,37,31,240,0],[408017,"Kiều Trọng Trọng","",1,0,0,2,100,120,120,17,20,16,20,0],[407365,"Quế Kính","",1,2,0,3,100,130,130,17,15,12,30,0],[346066,"Triệu Thành Hưng","",1,1,0,251,100,2610,2610,310,48,340,2510,7]]],[94703,"iwunu18(Đô Thành)",252,-232,[[351504,"Tấn Nhiếp Binh","",1,1,0,253,100,2630,2630,360,22,380,2530,8]]],[96319,"Thành mới của D2A | iwunu",268,-230,[]],[96320,"Thành mới của D2A | iwunu",266,-228,[]],[96321,"Thành mới của D2A | iwunu",264,-230,[]],[96322,"Thành mới của D2A | iwunu",267,-232,[]],[96323,"Thành mới của D2A | iwunu",264,-231,[]],[96324,"Thành mới của D2A | iwunu",265,-228,[]],[96325,"Thành mới của D2A | iwunu",269,-230,[]],[96871,"Thành mới của D2A | iwunu",268,-229,[]],[96872,"Thành mới của D2A | iwunu",269,-229,[]],[96873,"Thành mới của D2A | iwunu",269,-231,[]],[96874,"Thành mới của D2A | iwunu",267,-233,[]],[97071,"Thành mới của D2A | iwunu",262,-233,[]],[97328,"Thành mới của D2A | iwunu",263,-233,[]],[97667,"Thành mới của D2A | iwunu",263,-229,[]],[97670,"Thành mới của D2A | iwunu",261,-233,[]],[98934,"Thành mới của D2A | iwunu",254,-231,[]],[98935,"Thành mới của D2A | iwunu",254,-230,[]],[99767,"Test",253,-229,[[407420,"Thiên Kiệm","",1,1,0,16,100,260,260,41,32,19,160,6]]],[99768,"Thành mới của D2A | iwunu",253,-227,[]],[99769,"Thành mới của D2A | iwunu",252,-227,[]],[99770,"Thành mới của D2A | iwunu",251,-226,[]],[99771,"Thành mới của D2A | iwunu",253,-223,[]],[99772,"Thành mới của D2A | iwunu",252,-223,[]],[101072,"nhà vệ sinh",341,-262,[]],[101498,"iwunu21",271,-231,[[392490,"Lôi Hậu Hạnh","",1,1,0,150,100,1600,1600,170,90,250,1500,0]]],[101502,"iwunu22",261,-239,[[436356,"Hòa Trình Hảo","",1,0,0,56,100,660,660,50,44,36,560,0],[436357,"Huỳnh Hiên","",1,0,0,56,100,660,660,50,63,80,560,0],[436358,"Tư Trùng Văn","",1,0,0,55,100,650,650,95,34,39,550,0],[436359,"Lục Việt","",1,0,0,44,97,540,540,70,28,16,440,0],[436360,"Mộ Dung Hoa Khởi","",1,0,0,41,100,510,510,67,11,49,410,0],[436361,"Lỗ Ban","",1,0,0,56,100,660,660,93,20,50,560,0],[392491,"Nhược Hinh","",1,1,0,249,100,2590,2590,280,65,340,2490,6]]],[101514,"iwunu23",261,-251,[[367258,"Hạnh Tục Long","",1,1,0,146,100,1560,1560,160,73,230,1460,7]]],[103240,"Thành mới của D2A | iwunu",264,-249,[]],[103839,"Thành mới của D2A | iwunu",267,-251,[]],[104752,"bodi",401,-386,[[390592,"Chúc Văn Biên","",1,1,0,83,100,930,930,120,29,140,830,7]]],[105059,"o noi xa lam",-615,574,[]]]}
				/*List:
				 * 		0: Gen ID
						1: GeneralName 
						2: GeneralHistroryName 
						3: Generaltype	
				 *		4: ChucTuoc 
						5: GeneralStatus 
				 *		6: Level 
						7: MucTrungThanh 
						8: TheLucHienTai 
						9: TongTheLuc 
						10: ChiSoSucManh 
						11: ChiSoNhanhNhen 
						12 : ChiSoThongLinh 
				 *		13:
						14 : DiemCongConLai 				
				 */


				result.Clear();

				ArrayList incity;
				ArrayList genincity;
				int cityid;
				ArrayList onegen;
				for (int i = 0; i < list.Count; i++)
				{
					incity = (ArrayList)list[i];
					cityid = int.Parse(incity[0].ToString());
					genincity = (ArrayList)incity[4];
					miligen = new LVClient.Command.CityObj.CivilGeneral[genincity.Count];

					for (int j = 0; j < genincity.Count; j++)
					{
						onegen = (ArrayList)genincity[j];
						miligen[j] = new LVClient.Command.CityObj.CivilGeneral();
						miligen[j].CityID = cityid;
						miligen[j].CityName = incity[1].ToString();

						miligen[j].GeneralId = int.Parse(onegen[0].ToString());
						miligen[j].GeneralName = (onegen[1].ToString());
						miligen[j].GeneralHistroryName = (onegen[2].ToString());
						miligen[j].Generaltype = int.Parse(onegen[3].ToString());
						miligen[j].ChucTuoc = int.Parse(onegen[4].ToString());
						miligen[j].GeneralStatus = int.Parse(onegen[5].ToString());
						miligen[j].Level = int.Parse(onegen[6].ToString());
						miligen[j].MucTrungThanh = int.Parse(onegen[7].ToString());
						miligen[j].TheLucHienTai = int.Parse(onegen[8].ToString());
						miligen[j].TongTheLuc = int.Parse(onegen[9].ToString());
						miligen[j].ChiSoMiLuc = int.Parse(onegen[10].ToString());
						miligen[j].ChiSoMuuTri = int.Parse(onegen[11].ToString());
						miligen[j].ChiSoNoiChinh = int.Parse(onegen[12].ToString());
						miligen[j].DiemCongConLai = int.Parse(onegen[14].ToString());

					}

					result.Add(cityid, miligen);

				}
				return result;

			}
			catch (Exception ex)
			{
				return null;
			}
		}


		/// <summary>
		/// Lấy thông tin cơ bản về tướng như cấp, level, sức mạnh, thống lĩnh ... ở phần nội chính/nhân sự
		/// </summary>
		/// <returns>Hastable object. Key: cityID, Value: LVClient.Command.CityObj.MilitaryGeneral[] </returns>
		public static Hashtable GetAllSimpleMilitaryGeneralInfo()
		{
			try
			{
				LVClient.Command.CityObj.MilitaryGeneral[] miligen = null;

				Hashtable result = LVClient.Command.Common.Execute(32, "type=2", true);

				if (result == null || result["ret"].ToString() != "0") return null;
				ArrayList  list = (ArrayList ) result["list"];

				// quan vo
				// http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=32&0.1458047635938451&type=2
				//	{"ret":0,"list":[[10718,"iwunu7(Ðô thành)",255,-231,[[409793,"B?ch C?nh","",2,0,0,51,100,610,610,28,44,28,510,0],
				//[405710,"Âu Van M?","",2,0,0,49,100,590,590,79,80,87,490,0],[405714,"La Phòng","",2,0,0,64,100,740,740,30,81,85,640,0],
				//[405723,"Quân L?c Xuyên","",2,0,0,47,100,570,570,44,43,68,470,0],[397975,"*C?t T?n","*C?t T?n",2,0,0,106,100,1500,1500,150
				//,370,260,1060,4],[386274,"Trung Thành Thành","",2,0,0,57,97,670,670,78,76,14,570,0],[381228,"Giang Khôn Quán","",2,0,0,55,
				//100,650,650,69,48,26,550,0],[381229,"Tr?ng M?c","",2,0,0,55,100,650,650,96,82,51,550,0],[366355,"D2A","",2,0,0,52,100,620,
				//620,41,93,79,520,0],[367862,"Lam M?n Tích","",2,0,0,4,100,140,140,37,25,32,40,0],[368096,"D2A","",2,0,0,37,100,470,470,30,31,71,370,0],[368100,"D2A","",2,0,0,24,100,340,340,14,29,33,240,0],[357849,"H?ng Thanh","",2,0,0,29,100,390,390,49,31,31,290,0],[357999,"4","",2,0,0,6,100,160,160,47,34,12,60,0],[358062,"41","",2,0,0,42,100,520,520,83,44,35,420,0],[358085,"30","",2,0,0,43,100,530,530,40,59,79,430,0],[358087,"28","",2,0,0,38,100,480,480,69,78,31,380,0],[277645,"Tào Chuong*","Tào Chuong",2,0,16,267,97,3500,3500,500,500,600,2670,2],[276392,"Kh?ng L?c Di?c","",2,0,0,14,100,240,240,26,24,31,140,0],[276396,"T? L?c Bi?u","",2,0,0,25,100,350,350,45,20,19,250,0],[276398,"V?n H?u H?a Xuyên","",2,0,0,15,100,250,250,13,11,30,150,0],[276400,"Ð?ng Cách Quang","",2,0,0,31,100,410,410,56,22,62,310,0],[234507,"*Vuu Ð?t","*Vuu Ð?t",2,0,18,194,100,2380,2380,430,400,330,1940,13]]],[-42662,"7.1",-311,87,[[405742,"Su Cuong","",2,0,0,52,100,620,620,97,80,22,520,0]]],[-42670,"7.2",-312,85,[[412703,"Vu T?c Nghia","",2,0,0,2,100,120,120,15,13,13,20,0],[412704,"H?ng Ð?c","",2,0,0,3,100,130,130,10,11,10,30,0],[412999,"Thái B?c Thúy","",2,0,0,3,100,130,130,14,14,17,30,0],[413000,"Ð?m Thai Khai C?n","",2,0,0,9,100,190,190,13,22,13,90,0],[413427,"Tái Di?c Vân","",2,0,0,1,100,110,110,20,11,17,10,0],[366237,"Nhu?c ?i D?","",2,0,0,40,100,500,500,65,61,13,400,0],[363818,"Bùi Trung Thúy","",2,0,0,26,100,360,360,32,59,52,260,0],[275241,"2","",2,0,0,23,100,330,330,39,52,35,230,0]]],[13139,"iwunu5",265,-229,[[275162,"Thái S? T?*","Thái S? T?",2,0,0,285,100,3780,3780,550,660,545,2850,4],[426324,"Lão N?p Th?ch","",2,0,0,51,100,610,610,68,38,54,510,0],[412180,"1","",2,0,0,46,100,560,560,25,22,87,460,0],[412181,"2","",2,0,0,60,100,700,700,74,102,49,600,0],[412183,"D2A","",2,0,0,58,100,680,680,73,101,63,580,0],[405715,"D2A","",2,0,0,53,97,630,630,35,46,58,530,0],[405716,"D2A","",2,0,0,58,100,680,680,96,77,27,580,0],[405717,"D2A","",2,0,0,43,100,530,530,83,68,62,430,0],[406794,"D2A","",2,0,0,5,100,150,150,16,27,15,50,0],[406814,"D2A","",2,0,0,8,100,180,180,44,16,41,80,0],[404070,"D2A","",2,0,0,1,100,110,110,16,18,13,10,0],[404071,"D2A","",2,0,0,1,97,110,110,14,18,13,10,0],[302787,"*Nga Hà","*Nga Hà Thi?u Tru?ng",2,0,0,181,100,2250,2250,455,214,419,1810,0],[202618,"Qu?n H?i*","Qu?n H?i",2,0,0,229,100,2730,2730,610,150,600,2290,4],[167931,"*Ð?p Ð?n","*Ð?p Ð?n",2,0,0,151,100,1940,1940,306,406,213,1510,5]]],[-46538,"5.1",261,-228,[]],[-22800,"5.2",-311,85,[[277802,"1","",2,0,0,48,100,580,580,16,13,41,480,0],[277804,"2","",2,0,0,42,100,520,520,78,53,67,420,0],[277805,"3","",2,0,0,39,100,490,490,71,54,27,390,0],[277811,"12","",2,0,0,19,100,290,290,49,22,31,190,0],[271759,"2x","",2,0,0,47,100,570,570,73,76,33,470,0],[264831,"9","",2,0,0,52,100,620,620,20,36,83,520,0]]],[-16702,"5.3",-311,84,[[412227,"T? H?u","",2,0,0,65,100,750,750,55,83,87,650,0],[413428,"T?n B?i","",2,0,0,7,100,170,170,20,21,10,70,0],[413429,"T? Phu?ng Uy","",2,0,0,15,97,250,250,34,14,14,150,0],[413430,"L? Diêu","",2,0,0,3,100,130,130,16,17,13,30,0],[413431,"L?i Th?o Ph?m","",2,0,0,1,100,110,110,13,20,11,10,0],[413787,"Ba Thiêm Kính","",2,0,0,7,100,170,170,12,12,21,70,0],[413788,"T?t Ch?n","",2,0,0,1,97,110,110,10,19,18,10,0]]],[-14042,"5.4",262,-227,[[404072,"Ki?u Ð?c Phù","",2,0,0,4,100,140,140,14,13,13,40,0],[404073,"V?n C?n","",2,0,0,4,100,140,140,20,17,17,40,0],[400166,"Tu B?o Chi?n","",2,0,0,64,100,740,740,74,36,44,640,0],[386275,"Vân Kim","",2,0,0,57,100,670,670,22,74,46,570,0]]],[13835,"iwunu19(Ðô Thành)",259,-235,[[426276,"Ðào Khai","",2,0,0,17,100,270,270,50,14,36,170,0],[426277,"Dung Phong","",2,0,0,53,100,630,630,11,52,79,530,0],[426278,"Thái Ð?c Hàn","",2,0,0,23,97,330,330,41,59,47,230,0],[412229,"T?t Chi?n Vi","",2,0,0,50,100,600,600,86,94,62,500,0],[413449,"H? Ð?o Chiêu","",2,0,0,65,100,750,750,38,91,105,650,0],[413450,"Lu Vu Ðông","",2,0,0,64,97,740,740,94,36,29,640,0],[413451,"Chu Vu","",2,0,0,47,100,570,570,49,81,28,470,0],[413452,"Gia H?u Bá","",2,0,0,46,100,560,560,50,19,59,460,0],[413453,"Thám Tích","",2,0,0,3,100,130,130,40,35,24,30,0],[413454,"L? Luong","",2,0,0,13,100,230,230,37,13,17,130,0],[413456,"Võ Công","",2,0,0,63,100,730,730,10,18,69,630,0],[413457,"Gia Tho","",2,0,0,35,100,450,450,69,43,14,350,0],[413458,"Vi Hùng Luân","",2,0,0,20,97,300,300,55,22,18,200,0],[406812,"Chi?n D?","",2,0,0,6,100,160,160,39,49,10,60,0],[404201,"Quân Hi?n Kim","",2,0,0,6,100,160,160,17,12,10,60,0],[404202,"Ph?m Tr?c","",2,0,0,3,100,130,130,20,19,18,30,0],[404203,"Nguy?n Nam Lu?ng","",2,0,0,1,100,110,110,14,14,16,10,0],[404204,"H?a Di?c Ð?u","",2,0,0,8,100,180,180,25,10,12,80,0],[387105,"Hoàng H?i Buu","",2,0,0,39,100,490,490,10,45,13,390,0],[363928,"Vân Phàn Thúy","",2,0,0,25,100,350,350,55,26,33,250,0],[358086,"29","",2,0,0,30,100,400,400,22,26,42,300,0],[351888,"2","",2,0,0,19,100,290,290,16,10,35,190,0],[305020,"*Vi?t Cát","*Vi?t Cát",2,0,0,181,100,2250,2250,436,236,452,1810,2],[276382,"D2A","",2,0,0,2,100,120,120,21,33,30,20,0],[276386,"7","",2,0,0,27,97,370,370,10,55,56,270,0],[276393,"Mao Y?n Tinh","",2,0,0,26,100,360,360,37,18,35,260,0],[234480,"*Phí S?n","*Phí S?n",2,0,0,164,100,2080,2080,388,378,254,1640,7]]],[-46763,"19.1",-312,86,[]],[-44431,"19.2",-312,87,[[366171,"L? Khang","",2,0,0,2,100,120,120,17,24,20,20,0],[366235,"Lôi Trung Tho","",2,0,0,57,100,670,670,35,75,55,570,0],[363823,"Tuong Luu","",2,0,0,28,100,380,380,30,46,16,280,0],[243608,"M? N?p Ðinh","",2,0,0,1,100,110,110,14,13,11,10,0]]],[17485,"iwunu12(Ðô Thành)",265,-247,[[405188,"Quân TinhTh?t","",2,0,0,13,100,230,230,45,42,44,130,0],[405189,"T? Tuy?t","",2,0,0,14,100,240,240,31,40,35,140,0],[405190,"Lang Khang Th?n","",2,0,0,34,100,440,440,64,22,46,340,0],[405191,"T? M?c Khánh","",2,0,0,24,100,340,340,39,17,54,240,0],[405192,"Song Phàn Bá","",2,0,0,20,100,300,300,54,47,24,200,0],[405193,"Không M?","",2,0,0,32,97,420,420,40,38,24,320,0],[405194,"Ðông Phuong Tr? B?ch","",2,0,0,13,100,230,230,30,26,38,130,0],[405195,"Th?n Luu Y?n","",2,0,0,42,100,520,520,51,28,24,420,0],[405196,"Tùng Tr?","",2,0,0,12,97,220,220,38,23,30,120,0],[405197,"H? Ð?c H?u","",2,0,0,34,100,440,440,40,55,48,340,0],[405198,"Công Duong An Thiên","",2,0,0,20,100,300,300,44,45,28,200,0],[405199,"Hà Tr?ng Vi","",2,0,0,44,100,540,540,48,34,52,440,0],[405200,"Giang Th?","",2,0,0,35,97,450,450,50,51,55,350,0],[405244,"Chi?n T?ng Qu?","",2,0,0,6,100,160,160,19,20,14,60,0],[405263,"Ng?y Hi?u Hào","",2,0,0,41,100,510,510,21,65,12,410,0],[405731,"Vi?t C?nh Vi?t","",2,0,0,23,100,330,330,31,12,25,230,0],[405732,"Diêu Ð?c Ðông","",2,0,0,6,100,160,160,24,12,38,60,0],[405733,"Bành Ðan C?c","",2,0,0,13,97,230,230,23,31,49,130,0],[405734,"Phong Kính Khang","",2,0,0,48,100,580,580,82,19,10,480,0],[405735,"Tr?nh Kh?i Uy","",2,0,0,14,100,240,240,29,28,54,140,0],[405736,"Tái Uy Tho","",2,0,0,8,100,180,180,22,11,34,80,0],[405737,"Quách Tú H?o","",2,0,0,14,97,240,240,39,53,19,140,0],[406798,"Ngu B?o","",2,0,0,58,100,680,680,65,21,28,580,0],[406799,"Thành Hi?u Phàn","",2,0,0,63,100,730,730,44,74,20,630,0],[406800,"Lang Qúy H?o","",2,0,0,25,100,350,350,26,67,37,250,0],[406801,"Tôn D?ch L?c","",2,0,0,13,100,230,230,47,24,33,130,0],[406802,"K? H?nh","",2,0,0,41,100,510,510,69,54,45,410,0],[406803,"Hoàng Khai Qu?","",2,0,0,65,100,750,750,110,57,18,650,0],[406804,"Hoàn Kính","",2,0,0,30,100,400,400,62,57,27,300,0]]],[19357,"iwunu10(Ðô Thành)",254,-227,[[405719,"Cung Ð?ng Qu?ng","",2,0,0,47,100,570,570,41,43,21,470,0],[405720,"Ng?y Qu? An","",2,0,0,21,100,310,310,63,61,57,210,0],[405721,"Quách Th?c Ðinh","",2,0,0,43,100,530,530,33,68,45,430,0],[405722,"Cung Qu? Thành","",2,0,0,21,100,310,310,25,17,54,210,0],[405725,"Lão T? H?u","",2,0,0,8,100,180,180,17,51,34,80,0],[405726,"Vi Minh Tr?ch","",2,0,0,28,100,380,380,49,28,62,280,0],[405727,"Tô T?ch Huyên","",2,0,0,34,100,440,440,28,66,20,340,0],[405728,"Tòng Du","",2,0,0,60,100,700,700,37,12,31,600,0]]],[20118,"iwunu11(Ðô Thành)",265,-219,[]],[22604,"iwunu1(Ðô Thành)",261,-230,[[405711,"M?c Niên","",2,0,0,3,100,130,130,29,46,23,30,3],[405712,"Gia Cát Y?n Buu","",2,0,0,51,100,610,610,75,19,51,510,0],[405724,"Lang D?","",2,0,0,42,100,520,520,74,72,17,420,0],[405740,"M?nh Nguyên Du","",2,0,0,3,97,130,130,48,39,28,30,0],[405741,"Phàn Ki?n B?t","",2,0,0,10,100,200,200,38,25,31,100,0],[405743,"Ung Nguyên","",2,0,0,15,100,250,250,30,17,58,150,0],[405745,"Tri?u Ðon Linh","",2,0,0,43,100,530,530,20,46,83,430,0],[405746,"Van Nê Mai","",2,0,0,27,100,370,370,42,69,29,270,0],[387106,"Duong Tu?ng Van","",2,0,0,36,100,460,460,11,40,76,360,0],[303217,"*Tri?t Lý Cát","*Tri?t Lý Cát",2,0,0,177,100,2180,2180,478,220,431,1770,1],[276390,"Thúy Van","",2,0,0,32,100,420,420,24,39,30,320,0],[202784,"*M? Dung Hoàng","*M? Dung Hoàng",2,0,0,171,100,2140,2140,369,381,235,1710,5]]],[22881,"iwunu20(Ðô Thành)",279,-255,[[437599,"Công Th?c","",2,0,0,58,100,680,680,14,65,49,580,0],[437600,"Tri?u Ðoan","",2,0,0,55,100,650,650,76,66,35,550,0],[437601,"Tào N?p","",2,0,0,56,100,660,660,57,18,22,560,0],[437602,"Hoa L? B?ch","",2,0,0,57,100,670,670,47,90,89,570,0],[437603,"Vi?t Di?p Quang","",2,0,0,31,97,410,410,23,17,72,310,0],[437604,"M?nh Tú Cách","",2,0,0,34,100,440,440,20,40,28,340,0],[437605,"V? Th?ch Xuyên","",2,0,0,33,100,430,430,66,31,51,330,0],[405678,"?n Hinh Vân","",2,0,0,20,100,300,300,13,10,16,200,0],[405679,"H?u Tu?ng Nhã","",2,0,0,36,100,460,460,24,18,15,360,0],[405680,"Ngu Côn Buu","",2,0,0,43,100,530,530,80,16,71,430,0],[405682,"Hoài Ð?u H?i","",2,0,0,18,100,280,280,15,47,18,180,0],[405683,"Ô ?i","",2,0,0,6,100,160,160,28,37,26,60,0],[405685,"Hoàn Tr?ch Biên","",2,0,0,19,100,290,290,20,49,11,190,0],[405686,"Qu? Du","",2,0,0,42,100,520,520,12,43,67,420,0],[405687,"Công Duong Ð?nh","",2,0,0,52,97,620,620,91,59,41,520,0],[405688,"Luu Th?c Quy","",2,0,0,52,100,620,620,82,61,46,520,0],[405690,"L?c C?n Luân","",2,0,0,11,100,210,210,37,24,41,110,0],[405691,"Long C?n Nam","",2,0,0,21,100,310,310,10,44,28,210,0],[405692,"S? Ph?c M?c","",2,0,0,8,100,180,180,32,35,27,80,0],[405693,"Du Th? Phú","",2,0,0,46,100,560,560,21,47,85,460,0],[405694,"T?t Vân Thiên","",2,0,0,15,100,250,250,37,46,17,150,0],[405695,"Th?nh M? Ðinh","",2,0,0,44,100,540,540,66,39,69,440,0],[405696,"L? Tho B?n","",2,0,0,8,100,180,180,42,31,34,80,0],[405697,"H?ng Xuyên Tri?n","",2,0,0,17,100,270,270,37,41,23,170,0],[405699,"T?t Tr?ng Tr?","",2,0,0,4,100,140,140,29,29,33,40,0],[405700,"Dung B?t ?c","",2,0,0,39,100,490,490,55,33,77,390,0],[405701,"Giang Du Ð?c","",2,0,0,2,100,120,120,40,20,28,20,0],[405703,"Hàn Tr?ch Hinh","",2,0,0,50,97,600,600,18,39,39,500,0],[405704,"Nhi?m Hòa Linh","",2,0,0,1,100,110,110,29,10,36,10,0],[405706,"Vu Thiên","",2,0,0,21,100,310,310,37,26,17,210,0],[405707,"Nguyên H?i","",2,0,0,27,100,370,370,27,63,22,270,0]]],[23381,"iwunu2(Ðô Thành)",268,-247,[[407968,"T?ng Diêm","",2,0,0,53,100,630,630,19,84,51,530,0],[407971,"Khúc Bá An","",2,0,0,52,100,620,620,94,92,56,520,0],[407973,"Nam Cung Van","",2,0,0,59,100,690,690,20,73,61,590,0],[405273,"Châu Hung Quy","",2,0,0,4,100,140,140,18,11,19,40,0],[405274,"?n Du","",2,0,0,6,100,160,160,17,18,15,60,0],[405275,"Hà Nê Diêu","",2,0,0,2,100,120,120,16,17,14,20,0],[405276,"Tuong Du H?i","",2,0,0,1,100,110,110,15,16,12,10,0],[405277,"La Khang Ban","",2,0,0,6,100,160,160,23,18,16,60,0],[405278,"Tri?u Phong Cách","",2,0,0,7,100,170,170,13,20,10,70,0],[405279,"Phó Thành Vu","",2,0,0,8,100,180,180,23,22,23,80,0],[405280,"Li?u Kính Son","",2,0,0,5,97,150,150,15,19,10,50,0],[405281,"Cung Thành T?","",2,0,0,3,100,130,130,20,18,17,30,0],[405282,"Vân Phàn","",2,0,0,5,100,150,150,15,12,13,50,0],[405283,"Minh Tu?ng Hinh","",2,0,0,1,100,110,110,15,12,18,10,0]]],[-6265,"2. Thuc 4x4",-313,89,[[368101,"D2A","",2,0,0,27,100,370,370,25,14,11,270,0],[368102,"D2A","",2,0,0,42,100,520,520,41,34,34,420,0]]],[-4473,"2 Sat 3x3",-312,88,[]],[28200,"iwunu13(Ðô Thành)",270,-264,[[437486,"Âm Th?o M?c","",2,0,0,44,100,540,540,81,42,52,440,0],[437487,"Ph?m Khôn B?ch","",2,0,0,59,100,690,690,76,86,100,590,0],[437488,"Kim Ban","",2,0,0,63,100,730,730,24,90,51,630,0],[437489,"Kim Tu?ng","",2,0,0,50,97,600,600,15,94,62,500,0],[437490,"T? Ð?ng Cách","",2,0,0,24,100,340,340,61,12,25,240,0],[437491,"Quân Cô Minh","",2,0,0,27,100,370,370,31,10,57,270,0],[437492,"Lang Ðinh Tr?ch","",2,0,0,24,97,340,340,42,37,17,240,0],[405311,"Ph?m Ninh Minh","",2,0,0,3,100,130,130,30,21,37,30,0],[405312,"Chi?n Nê B?ch","",2,0,0,25,100,350,350,11,36,55,250,0],[405314,"Hoàng C?nh Luân","",2,0,0,24,100,340,340,46,41,10,240,0],[405317,"Ng? Biên Thúy","",2,0,0,5,100,150,150,12,12,12,50,0],[405318,"Quân Lu?ng Hoài","",2,0,0,23,100,330,330,29,22,11,230,0],[405319,"Ph?m Nh?n L?","",2,0,0,1,100,110,110,23,19,29,10,0],[405851," Khang L?c Tuy?t","",2,0,0,7,100,170,170,41,32,31,70,0],[405852,"Hòa Bá Phú","",2,0,0,59,100,690,690,96,18,62,590,0],[405853,"Long Tuy?t Nam","",2,0,0,4,100,140,140,21,21,41,40,0],[405854,"Lu Kì Tr?ch","",2,0,0,8,100,180,180,35,41,45,80,0],[405855,"Lâm Trùng L?","",2,0,0,29,100,390,390,59,29,48,290,0],[405856,"Su Vân Binh","",2,0,0,39,100,490,490,26,39,33,390,0],[405857,"Quách Qu?ng Long","",2,0,0,3,100,130,130,13,24,32,30,0],[405858,"Nguyên Hòa Qu?ng","",2,0,0,15,100,250,250,50,29,18,150,0],[405859,"Ði?n Pháp","",2,0,0,4,100,140,140,16,39,43,40,0],[405860,"T?nh Tuy?n Hi?p","",2,0,0,50,100,600,600,69,46,64,500,0],[405861,"S? Phù Vu","",2,0,0,55,100,650,650,45,75,40,550,0],[405862,"Long Niên","",2,0,0,21,100,310,310,23,62,60,210,0],[405863,"D?ch Cách ?i","",2,0,0,29,100,390,390,15,13,40,290,0],[407009,"Na Nguyên Hoàng","",2,0,0,55,100,650,650,19,51,66,550,0],[367852,"H? H?u H?u","",2,0,0,7,100,170,170,39,15,24,70,0],[367853,"Nam Cung H?ng Tây","",2,0,0,21,100,310,310,13,26,46,210,0],[367854,"Tu Hào Công","",2,0,0,32,100,420,420,25,37,10,320,0],[367855,"Bàng Ðoan","",2,0,0,2,100,120,120,28,30,36,20,0],[367856,"Ðào Tây Tr?ch","",2,0,0,25,100,350,350,18,35,48,250,0],[367857,"Thu Xuân Lâm","",2,0,0,43,100,530,530,65,64,60,430,0]]],[34254,"iwunu3(Ðô Thành)",268,-244,[[408129,"Hoàng Vi?t","",2,0,0,4,97,140,140,43,37,27,40,0],[408130,"Long Hi?u Bích","",2,0,0,37,100,470,470,74,26,58,370,0],[408131,"H? H?u Luân Viên","",2,0,0,36,97,460,460,79,23,38,360,0],[408132,"H? H?i Qu?ng","",2,0,0,58,100,680,680,21,66,61,580,0],[408133,"Ung B?n Di?p","",2,0,0,33,100,430,430,72,75,29,330,0],[408134,"Hoài Th?t","",2,0,0,46,100,560,560,89,32,58,460,0],[408135,"Du Ki?n","",2,0,0,24,100,340,340,37,37,10,240,0],[408136,"Bàng Di?c Phòng","",2,0,0,52,100,620,620,71,82,73,520,0],[408137,"Gia Luong","",2,0,0,30,100,400,400,57,21,70,300,0],[408138,"Âm Phuong Ki?m","",2,0,0,54,100,640,640,88,25,51,540,0],[408139,"Tào ?c Huong","",2,0,0,15,100,250,250,42,46,52,150,0],[408140,"Tri?u Trung Quy","",2,0,0,53,100,630,630,66,10,30,530,0],[408141,"Bàng Niên M?c","",2,0,0,24,100,340,340,16,21,35,240,0],[408142,"Liêm Phàn Phòng","",2,0,0,16,97,260,260,27,33,55,160,0],[408143,"Ð?m Thai Quán Phòng","",2,0,0,22,100,320,320,30,41,36,220,0],[408144,"Kh? Hoài CamCác","",2,0,0,63,100,730,730,40,34,58,630,0],[408145,"Thi B?","",2,0,0,41,100,510,510,50,36,83,410,0],[408146,"Trang Phu?ng","",2,0,0,16,100,260,260,22,57,39,160,0],[408147,"Gi?n Qu? Tây","",2,0,0,42,100,520,520,76,29,73,420,0],[408148,"Khúc Qúy","",2,0,0,1,100,110,110,40,17,10,10,0],[408300,"Ngu D? M?n","",2,0,0,4,97,140,140,32,21,15,40,0],[405285,"T?nh C?nh Qu?ng","",2,0,0,7,100,170,170,16,26,11,70,0],[405286,"M?nh An Tr?","",2,0,0,4,100,140,140,25,15,16,40,0],[405287,"Lâm Tr?ch M?c","",2,0,0,9,100,190,190,19,16,16,90,0],[405288,"M?nh N?p Kính","",2,0,0,6,100,160,160,26,18,18,60,0],[405289,"Thành H?o Tr?c","",2,0,0,8,100,180,180,22,31,20,80,0],[405290,"Hoa K?","",2,0,0,9,100,190,190,17,18,28,90,0],[405291,"Qu? Hoài Phù","",2,0,0,11,100,210,210,18,25,13,110,0],[405292,"H?a Viên Ki?m","",2,0,0,9,100,190,190,30,18,11,90,0],[405293,"Quân An","",2,0,0,11,100,210,210,30,24,15,110,0],[405294,"Phong Khôn Bi?u","",2,0,0,4,100,140,140,15,26,12,40,0]]],[39557,"iwunu14(Ðô Thành)",294,-265,[[469089,"Hòa Th?o","",2,0,0,65,97,750,750,98,73,39,650,0],[469090,"Tr? B?o","",2,0,0,64,100,740,740,22,12,58,640,0],[469091,"Tri?u Ð?u Ngu","",2,0,0,58,100,680,680,15,40,67,580,0],[405484,"Phí Tiêu Quang","",2,0,0,17,100,270,270,43,10,54,170,0],[405489,"L?c Th?ch Phi","",2,0,0,22,100,320,320,20,40,20,220,0],[405492,"C? Hinh Tinh","",2,0,0,1,100,110,110,40,22,26,10,0],[405497,"Quân Van Ð?u","",2,0,0,60,97,700,700,21,13,95,600,0],[405500,"Nhan Thiêm","",2,0,0,51,100,610,610,78,38,30,510,0],[405501,"D?ch H?a","",2,0,0,14,100,240,240,47,10,49,140,0],[405503,"Phùng Tích","",2,0,0,42,97,520,520,80,60,84,420,0],[405504,"Khâu Ban Niên","",2,0,0,51,100,610,610,12,58,29,510,0],[406084,"Truong Tr?ch Ð?","",2,0,0,42,100,520,520,24,38,34,420,0],[406085,"Nhan Son Không","",2,0,0,51,100,610,610,70,15,20,510,0],[406086,"Hành Ki?n D?","",2,0,0,4,100,140,140,12,12,22,40,0],[406088,"H?nh Ð? Qu?ng","",2,0,0,44,100,540,540,15,24,10,440,0],[406089,"Biên Phúc Ðông","",2,0,0,51,100,610,610,17,33,53,510,0],[406146,"Mao Tuy?t","",2,0,0,18,100,280,280,28,35,47,180,0],[406147,"M? Dung B?n M?o","",2,0,0,29,100,390,390,67,65,16,290,0],[406148,"Bành Trùng Th?n","",2,0,0,19,100,290,290,34,13,34,190,0],[406149,"Hoa Tr?ch Nguyên","",2,0,0,31,100,410,410,69,14,39,310,0],[406150,"T?n Ð? Bang","",2,0,0,22,100,320,320,63,37,31,220,0],[406151,"Du Tú D?ch","",2,0,0,16,100,260,260,27,49,59,160,0],[406152,"Ph?m Ðinh H?u","",2,0,0,17,100,270,270,10,22,52,170,0],[406153,"H? Th?nh L?c","",2,0,0,47,100,570,570,28,21,12,470,0],[406154,"Võ Côn Tri?n","",2,0,0,14,100,240,240,55,36,52,140,0],[406155,"Tuong Ð?o","",2,0,0,22,100,320,320,23,36,22,220,0],[406156,"Nghiêm Kính Ð?nh","",2,0,0,28,100,380,380,34,20,61,280,0],[406157,"H?u Bích Uy","",2,0,0,57,100,670,670,62,45,92,570,0],[406158,"Du Vi?t Ð?u","",2,0,0,7,100,170,170,12,40,22,70,0],[406159,"ÁiThành","",2,0,0,23,97,330,330,50,13,41,230,0],[406160,"Ðu?ng Vân T?ng","",2,0,0,8,100,180,180,14,26,10,80,0],[406161,"Gia B?t Khai","",2,0,0,46,100,560,560,68,84,52,460,0],[402264,"S? Ao","",2,0,0,39,100,490,490,57,54,36,390,0]]],[40539,"iwunu4(Ðô Thành)",258,-231,[[430080,"Tào Bích","",2,0,0,41,100,510,510,57,70,36,410,0],[430081,"C? Phù Lan","",2,0,0,4,100,140,140,42,17,37,40,0],[404211,"Vu Phòng","",2,0,0,9,100,190,190,22,24,14,90,0],[400167,"Th?y Tu?ng","",2,0,0,54,100,640,640,74,76,15,540,0],[400169,"Th?y Không Cuong","",2,0,0,40,100,500,500,45,19,22,400,0],[400170,"Chi Tú Ph?m","",2,0,0,39,100,490,490,69,16,60,390,0],[400171,"Vuong Tr? Ð?ng","",2,0,0,39,97,490,490,12,30,65,390,0],[400172,"Long Tr? M?n","",2,0,0,42,100,520,520,75,79,85,420,0],[400173,"Lâm An D?c","",2,0,0,62,100,720,720,43,49,78,620,0],[400174,"H?a Th?c C?n","",2,0,0,48,100,580,580,10,89,23,480,0],[400175,"Chuong Xuân Hi?u","",2,0,0,38,100,480,480,31,34,83,380,0],[400176,"Phàn B?c Phú","",2,0,0,62,100,720,720,83,75,12,620,0],[400177,"Mao K?","",2,0,0,32,100,420,420,17,52,38,320,0],[400178,"H? H?u M?o","",2,0,0,21,100,310,310,27,35,55,210,0],[400179,"L?i Du N?p","",2,0,0,15,100,250,250,58,46,17,150,0],[400180,"Nhi?m Tr?ch Tri?n","",2,0,0,24,100,340,340,43,60,51,240,0],[400181,"Phùng Du Ki?n","",2,0,0,12,97,220,220,13,46,13,120,0],[400182,"L? Phù","",2,0,0,4,100,140,140,29,13,31,40,0],[400183,"Toàn H?i","",2,0,0,53,100,630,630,14,67,46,530,0],[400184,"Công Nghia","",2,0,0,16,100,260,260,19,34,34,160,0],[400185,"Long M? Nguyên","",2,0,0,60,100,700,700,26,70,86,600,0],[375025,"Phán Th?c Th?t","",2,0,0,58,97,680,680,47,81,69,580,0],[365681,"D2A","",2,0,0,5,100,150,150,49,29,27,50,0],[368099,"D2A","",2,0,0,61,97,710,710,93,46,81,610,0],[350696,"Cung C?n Diêm","",2,0,0,32,100,420,420,49,56,45,320,0],[313841,"Ð? D?*","Ð? D?",2,0,0,253,100,3170,3170,700,140,700,2530,2],[276387,"8","",2,0,0,37,97,470,470,53,12,30,370,0],[276388,"11","",2,0,0,34,100,440,440,39,24,46,340,0],[234453,"*T? Lang","*T? Lang",2,0,0,175,100,2190,2190,409,361,274,1750,6]]],[-46773,"4.1",-311,86,[]],[-42517,"4.2",-311,88,[[413785,"Ngô Di?c B?","",2,0,0,14,100,240,240,30,31,31,140,0],[413786,"M? Dung Nh?n D?c","",2,0,0,1,100,110,110,11,18,22,10,0],[404210,"Trang Th?o","",2,0,0,3,100,130,130,13,15,12,30,0],[377940,"Cát M? Quang","",2,0,0,55,100,650,650,33,30,37,550,0]]],[46999,"iwunu17(Ðô Thành)",273,-260,[[408220,"Thúy Luân","",2,0,0,28,100,380,380,57,57,17,280,0],[408221,"H?u Nh?n","",2,0,0,17,100,270,270,47,33,37,170,0],[408222,"Thúy Qu?ng Ð?nh","",2,0,0,30,97,400,400,28,74,20,300,0],[408223,"M? Kh?i Tri?n","",2,0,0,6,100,160,160,34,32,44,60,0],[408224,"Phùng H?u Bang","",2,0,0,5,100,150,150,41,15,34,50,0],[408225,"Tr?nh Th?nh Ki?n","",2,0,0,36,100,460,460,55,39,15,360,0],[408226,"Mã Khang T?n","",2,0,0,34,100,440,440,22,73,20,340,0],[408227,"?n Ki?n","",2,0,0,48,97,580,580,26,65,78,480,0],[408228,"Tri?u Ðinh Ðon","",2,0,0,29,100,390,390,28,46,58,290,0],[408229,"Quân Bi?u","",2,0,0,29,100,390,390,57,17,23,290,0],[408231,"Quan Th? C?c","",2,0,0,11,100,210,210,12,37,32,110,0],[408232,"Kh? Ð?nh","",2,0,0,31,100,410,410,46,56,54,310,0],[408233,"H?a T?c Kh?i","",2,0,0,26,100,360,360,33,66,56,260,0],[408234,"L?c Tuy?t Ngu","",2,0,0,8,100,180,180,10,34,48,80,0],[405251,"Chu Qúy Hoàng","",2,0,0,3,100,130,130,18,16,20,30,0],[405323,"Phùng Tho Bi?u","",2,0,0,8,100,180,180,31,19,18,80,0],[405324,"T? Phù","",2,0,0,9,100,190,190,38,44,39,90,0],[405325,"La Diêm","",2,0,0,27,100,370,370,49,43,23,270,0],[405327,"Hòa T?ng","",2,0,0,11,100,210,210,33,27,41,110,0],[405328,"Tu Ð? Phú Vu","",2,0,0,23,97,330,330,35,48,27,230,0],[405330,"Nhan Biên Tr?c","",2,0,0,32,100,420,420,62,39,67,320,0],[405331,"Gi?n Phong Th?","",2,0,0,16,100,260,260,49,10,26,160,0],[405753,"L? Biên Diêu","",2,0,0,44,100,540,540,75,24,20,440,0],[405754,"Gia Ð?nh ?c","",2,0,0,3,100,130,130,43,27,37,30,0],[405755,"Th?n ?c Ph?c","",2,0,0,19,100,290,290,30,12,33,190,0],[405756,"Song Diêm Hi?n","",2,0,0,2,100,120,120,13,40,31,20,0],[405758,"Khuong Pháp C?c","",2,0,0,3,100,130,130,18,26,16,30,0],[405760,"Hoa Kính Trùng","",2,0,0,32,97,420,420,70,53,61,320,0],[365419,"Phán Kiên Kì","",2,0,0,3,100,130,130,17,28,18,30,0]]],[75587,"iwunu6(Ðô Thành)",264,-238,[]],[83080,"iwunu8(Ðô Thành)",265,-253,[[408265,"Công Duong Th?n An","",2,0,0,65,100,750,750,32,73,54,650,0],[408267,"Song Khánh T?","",2,0,0,43,100,530,530,21,57,37,430,0],[408268,"Phuong Ki?m CamCác","",2,0,0,56,100,660,660,51,32,34,560,0],[408269,"H? H?u B?o B?","",2,0,0,63,97,730,730,83,65,21,630,0],[408270,"Lâm Cô","",2,0,0,41,100,510,510,40,68,71,410,0],[408271,"Viên Trình Hoài","",2,0,0,46,100,560,560,46,35,57,460,0],[408272,"Châu Hào Thiên","",2,0,0,10,100,200,200,54,22,35,100,0],[408273,"Nhan Trung M?c","",2,0,0,51,100,610,610,77,64,36,510,0],[408274,"Du Tr?c Cách","",2,0,0,39,97,490,490,82,25,31,390,0],[408275,"Khuong Cuong","",2,0,0,13,100,230,230,53,58,53,130,0],[408276,"Gia Túc Ð?u","",2,0,0,14,100,240,240,46,15,47,140,0],[408277,"Cung Bá D?ch","",2,0,0,56,100,660,660,30,28,83,560,0],[408278,"V?n Kh?i","",2,0,0,27,100,370,370,24,15,55,270,0],[408279,"Song H?o Ðan","",2,0,0,49,100,590,590,65,26,45,490,0],[408280,"K? Chiêu Túc","",2,0,0,27,100,370,370,24,34,29,270,0],[408281,"Ng? D?c","",2,0,0,33,100,430,430,18,40,29,330,0],[408282,"M?c Nguyên Cách","",2,0,0,5,100,150,150,41,30,40,50,0],[408283,"Hán Tu?ng Hùng","",2,0,0,42,100,520,520,24,61,11,420,0],[408284,"Ð?m Thai Quy","",2,0,0,60,100,700,700,69,71,54,600,0],[405295,"Th?y Luu","",2,0,0,1,100,110,110,10,10,12,10,0],[405296,"Hu?nh Qu?ng M?c","",2,0,0,7,100,170,170,23,17,12,70,0],[405297,"Na T?ng","",2,0,0,1,100,110,110,12,14,11,10,0],[405298,"Nguyên Nguyên Ban","",2,0,0,1,100,110,110,10,10,13,10,0],[405299,"Tu Ð? T?ng","",2,0,0,1,97,110,110,14,13,10,10,0],[405300,"Na H?nh","",2,0,0,1,100,110,110,13,12,10,10,0],[405301,"Ði?n Tú La","",2,0,0,2,97,120,120,22,12,22,20,0],[405302,"M?nh D?ch Di?p","",2,0,0,6,100,160,160,23,29,18,60,0],[405303,"Qu?c Di?p M?c","",2,0,0,2,100,120,120,20,15,21,20,0],[405304,"Vuong T?ng","",2,0,0,12,100,220,220,22,14,25,120,0],[405305,"Dung Diêm","",2,0,0,19,100,290,290,23,40,44,190,0],[405307,"Kim Uy Tinh","",2,0,0,4,97,140,140,12,11,16,40,0],[405308,"Dung Phu?ng Thành","",2,0,0,17,100,270,270,16,35,12,170,0],[405309,"Khuông B?i Khôn","",2,0,0,12,100,220,220,13,18,23,120,0]]],[83365,"iwunu9(Ðô Thành)",252,-224,[]],[93917,"iwunu15(Ðô Thành)",256,-239,[]],[93938,"iwunu16(Ðô Thành)",264,-250,[[405265,"Không Th?nh An","",2,0,0,9,100,190,190,11,14,15,90,0],[405267,"Th?n Ngu","",2,0,0,4,100,140,140,11,14,22,40,0],[405268,"H?nh Uy Tr?","",2,0,0,2,100,120,120,19,13,14,20,0],[405616,"Dung Ban","",2,0,0,9,100,190,190,15,29,25,90,0],[405618,"Trang B?i","",2,0,0,8,100,180,180,25,18,11,80,0],[405619,"Ti?n Ð?u Mai","",2,0,0,4,100,140,140,25,25,30,40,0],[405621,"Ph?m Bá Cách","",2,0,0,10,100,200,200,26,25,11,100,0],[405622,"Vu B?c Ð?ng","",2,0,0,11,100,210,210,27,27,10,110,0],[405623,"Cát Tr?c Ban","",2,0,0,22,100,320,320,17,44,14,220,0],[405624,"Lang Kh?i Nghiêm","",2,0,0,12,100,220,220,31,31,22,120,0],[405625,"H? H?u Lan H?o","",2,0,0,27,100,370,370,47,31,23,270,0],[405748,"Công Luong Hi?u","",2,0,0,10,100,200,200,26,10,33,100,0],[405749,"Thúy Kì Bích","",2,0,0,7,100,170,170,35,28,33,70,0],[405750,"Phùng Vu","",2,0,0,11,97,210,210,18,40,25,110,0],[404632,"Kh? Tr?ch Khang","",2,0,0,9,100,190,190,18,20,26,90,0],[404634,"Trung Nh?n","",2,0,0,1,100,110,110,11,17,16,10,0],[404635,"Nhi?m Y?n Kì","",2,0,0,9,100,190,190,22,25,17,90,0]]],[94703,"iwunu18(Ðô Thành)",252,-232,[[408166,"M? Dung Hiên","",2,0,0,17,100,270,270,26,30,28,170,0],[408167,"Chi?n Hùng Vân","",2,0,0,6,100,160,160,10,22,11,60,0],[408168,"Khúc C?n","",2,0,0,17,100,270,270,18,46,41,170,0],[408169,"Hành Th?n H?i","",2,0,0,25,100,350,350,23,15,50,250,0],[408170,"Ði?n T?ch Uy","",2,0,0,7,100,170,170,26,26,30,70,0],[408171,"Minh M? Ð?o","",2,0,0,1,100,110,110,11,21,17,10,0],[408172,"Mã Quang Kh?i","",2,0,0,19,100,290,290,46,46,31,190,0],[408173,"T? L? M?o","",2,0,0,5,100,150,150,23,21,25,50,0],[408174,"Vân N?p Nghiêm","",2,0,0,21,100,310,310,16,31,23,210,0],[408175,"Quân Biên Thành","",2,0,0,24,100,340,340,23,44,42,240,0],[408176,"Chúc Van Hi","",2,0,0,22,100,320,320,17,46,50,220,0],[408177,"Quân Tr?ch T?c","",2,0,0,29,100,390,390,11,38,53,290,0],[408178,"Hoa Th?c Pháp","",2,0,0,18,100,280,280,41,39,16,180,0],[408179,"Hán Lu?ng Viên","",2,0,0,7,97,170,170,29,11,33,70,0],[408180,"Ng? N?p Hung","",2,0,0,23,100,330,330,16,21,52,230,0],[408181,"T? Cung Nghia","",2,0,0,33,100,430,430,17,40,11,330,0],[408182,"Kh? Lu?ng","",2,0,0,28,100,380,380,50,16,36,280,0]]],[96319,"Thành m?i c?a D2A | iwunu",268,-230,[]],[96320,"Thành m?i c?a D2A | iwunu",266,-228,[]],[96321,"Thành m?i c?a D2A | iwunu",264,-230,[]],[96322,"Thành m?i c?a D2A | iwunu",267,-232,[]],[96323,"Thành m?i c?a D2A | iwunu",264,-231,[]],[96324,"Thành m?i c?a D2A | iwunu",265,-228,[]],[96325,"Thành m?i c?a D2A | iwunu",269,-230,[]],[96871,"Thành m?i c?a D2A | iwunu",268,-229,[]],[96872,"Thành m?i c?a D2A | iwunu",269,-229,[]],[96873,"Thành m?i c?a D2A | iwunu",269,-231,[]],[96874,"Thành m?i c?a D2A | iwunu",267,-233,[]],[97071,"Thành m?i c?a D2A | iwunu",262,-233,[]],[97328,"Thành m?i c?a D2A | iwunu",263,-233,[]],[97667,"Thành m?i c?a D2A | iwunu",263,-229,[]],[97670,"Thành m?i c?a D2A | iwunu",261,-233,[]],[98934,"Thành m?i c?a D2A | iwunu",254,-231,[]],[98935,"Thành m?i c?a D2A | iwunu",254,-230,[]],[99766,"Thành m?i c?a D2A | iwunu",253,-228,[]],[99767,"Thành m?i c?a D2A | iwunu",253,-229,[]],[99768,"Thành m?i c?a D2A | iwunu",253,-227,[]],[99769,"Thành m?i c?a D2A | iwunu",252,-227,[]],[99770,"Thành m?i c?a D2A | iwunu",251,-226,[]],[99771,"Thành m?i c?a D2A | iwunu",253,-223,[]],[99772,"Thành m?i c?a D2A | iwunu",252,-223,[]],[101072,"nhà v? sinh",341,-262,[]],[101498,"iwunu21",271,-231,[]],[101502,"iwunu22",261,-239,[]],[101514,"iwunu23",261,-251,[]],[103240,"Thành m?i c?a D2A | iwunu",264,-249,[]],[103839,"Thành m?i c?a D2A | iwunu",267,-251,[]],[104752,"bodi",401,-386,[[413778,"Cung Ð?nh Nh?n","",2,0,0,12,100,220,220,13,23,13,120,0],[413779,"Chuong Khai Ð?u","",2,0,0,1,100,110,110,19,21,16,10,0],[413780,"Nguyên Pháp Phu?ng","",2,0,0,13,97,230,230,30,17,29,130,0],[413781,"Hành Tiêu Ð?c","",2,0,0,14,100,240,240,11,13,15,140,0],[413782,"Quân Tuy?n Cô","",2,0,0,13,100,230,230,19,21,21,130,0],[413784,"K? Lan Tinh","",2,0,0,11,100,210,210,16,19,10,110,0]]],[105059,"o noi xa lam",-615,574,[]]]}


				/*List:
				 * 		0: Gen ID
						1: GeneralName 
						2: GeneralHistroryName 
						3: Generaltype	
				 *		4: ChucTuoc 
						5: GeneralStatus 
				 *		6: Level 
						7: MucTrungThanh 
						8: TheLucHienTai 
						9: TongTheLuc 
						10: ChiSoSucManh 
						11: ChiSoNhanhNhen 
						12 : ChiSoThongLinh 
				 *		13:
						14 : DiemCongConLai 				
				 */

				result.Clear();

				ArrayList incity;
				ArrayList genincity;
				int cityid;
				ArrayList onegen ;
				for (int i = 0; i < list.Count; i++)
				{
					incity = (ArrayList) list[i];
					cityid = int.Parse( incity[0].ToString());
					genincity = (ArrayList)incity[4];
					miligen = new LVClient.Command.CityObj.MilitaryGeneral[genincity.Count];

					for (int j = 0; j < genincity.Count; j++)
					{
						onegen = (ArrayList) genincity[j];
						miligen[j] = new LVClient.Command.CityObj.MilitaryGeneral();
						miligen[j].CityID = cityid;
						miligen[j].CityName = incity[1].ToString(); 
						
						miligen[j].GeneralId = int.Parse	(onegen[0].ToString());
						miligen[j].GeneralName =			(onegen[1].ToString());
						miligen[j].GeneralHistroryName =	(onegen[2].ToString());
						miligen[j].Generaltype	=	int.Parse (onegen[3].ToString());
						miligen[j].ChucTuoc =		int.Parse(onegen[4].ToString());
						miligen[j].GeneralStatus = int.Parse(onegen[5].ToString());
						miligen[j].Level =			int.Parse(onegen[6].ToString());
						miligen[j].MucTrungThanh = int.Parse(onegen[7].ToString());
						miligen[j].TheLucHienTai = int.Parse(onegen[8].ToString());
						miligen[j].TongTheLuc = int.Parse(onegen[9].ToString());
						miligen[j].ChiSoSucManh = int.Parse(onegen[10].ToString());
						miligen[j].ChiSoNhanhNhen = int.Parse(onegen[11].ToString());
						miligen[j].ChiSoThongLinh = int.Parse(onegen[12].ToString());
						miligen[j].DiemCongConLai = int.Parse(onegen[14].ToString());

					}

					result.Add(cityid, miligen);

				}
				return result;

			}
			catch (Exception ex)
			{
				return null;
			}
		}

		// Laays thong tin ve tuong trong thanh/trai
		// tra ve Arraylist of Command.CityObj.General 
		public static ArrayList GetAllGeneralVanVo(int cityID)
		{
			int count = 0;
						
			Hashtable general = new Hashtable();
			string parameter = "";
			parameter += "ltype=4";
			parameter += "&tid=";
			//general = Execute(15, parameter, true);

			
			//int cityID = Command.CityObj.City.AllCity[citypos].id;
			//LVClient.Command.City.SwitchCitySlow(cityID);
			string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
			while (count < 10)
			{
				// lay danh sach quan van + quan vo
				general = Execute(15, parameter, true, cookies);
				if (general != null) break;

				count++;
				System.Threading.Thread.Sleep(1000);
			}
			try
			{
				ArrayList incity = (ArrayList)general["generals"];

				//Hungtv rem
				//Command.CityObj.City.AllCity[citypos].AllGeneral = new LVClient.Command.CityObj.General[incity.Count];

				ArrayList oneincity = null;
				ArrayList genList = new ArrayList();
				int j = 0;

				Command.CityObj.MilitaryGeneral g;
				for (int i = 0; i < incity.Count; i++)
				{
					//ArrayList oneincity = (ArrayList)incity[i];
					oneincity = (ArrayList)incity[i];

					//if (oneincity[4].ToString() == "2")				//=2: quan vo; =1: quan van
					{
						g = new LVClient.Command.CityObj.MilitaryGeneral();
						g.GeneralId = int.Parse(oneincity[0].ToString());
						g.GeneralName = (string)oneincity[1];
						g.GeneralStatus = int.Parse(oneincity[5].ToString());
						g.Generaltype = int.Parse(oneincity[4].ToString()); 
						genList.Add(g);
						//Command.CityObj.City.AllCity[citypos].AllGeneral[j] = g;

						j++;
					}
				}

				return genList;
			}
			catch (Exception erx)
			{
				return  null;
			}
		}

		// Laays thong tin ve tuong trong thanh/trai
		public static void GetUpdateGeneral(int citypos)
		{
			lock (GeneralisLock)
			{
				int count = 0;



				Hashtable hashnewgeneral = new Hashtable();
				string parameter = "";
				parameter += "ltype=4";
				parameter += "&tid=";
				//general = Execute(15, parameter, true);

				int cityID = Command.CityObj.City.AllCity[citypos].id;
				//LVClient.Command.City.SwitchCitySlow(cityID);
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
				while (count < 10)
				{
					// lay danh sach quan van + quan vo
					hashnewgeneral = Execute(15, parameter, true, cookies);
					if (hashnewgeneral != null) break;

					count++;
					System.Threading.Thread.Sleep(1000);
				}

				if (hashnewgeneral == null) return;

				try
				{
					ArrayList incity = (ArrayList)hashnewgeneral["generals"];

					//Hungtv rem
					//Command.CityObj.City.AllCity[citypos].AllGeneral = new LVClient.Command.CityObj.General[incity.Count];

					ArrayList oneincity = null;
					ArrayList genList = new ArrayList();
					int j = 0;

					Command.CityObj.MilitaryGeneral newg;
					Command.CityObj.MilitaryGeneral[] oldg = Command.CityObj.City.AllCity[citypos].MilitaryGeneral;
					int gtempid;
					for (int i = 0; i < incity.Count; i++)
					{
						//ArrayList oneincity = (ArrayList)incity[i];
						oneincity = (ArrayList)incity[i];
						newg = null;
						if (oneincity[4].ToString() == "2")				//=2: quan vo; =1: quan van
						{
							gtempid = int.Parse(oneincity[0].ToString());	// id tuong moi
							// tim tuong cu
							if (oldg != null)
							{
								for (int k = 0; k < oldg.Length; k++)
								{
									if (((Command.CityObj.MilitaryGeneral)oldg[k]).GeneralId == gtempid)
									{
										newg = oldg[k];
										break;
									}
								}
							}

							if (newg == null)
								newg = new LVClient.Command.CityObj.MilitaryGeneral();


							newg.GeneralId = int.Parse(oneincity[0].ToString());
							newg.GeneralName = (string)oneincity[1];
							newg.GeneralStatus = int.Parse(oneincity[5].ToString());
							genList.Add(newg);
							//Command.CityObj.City.AllCity[citypos].AllGeneral[j] = g;

							j++;
						}
					}

					Command.CityObj.City.AllCity[citypos].MilitaryGeneral = new LVClient.Command.CityObj.MilitaryGeneral[genList.Count];
					for (int i = 0; i < genList.Count; i++)
					{
						Command.CityObj.City.AllCity[citypos].MilitaryGeneral[i] = (LVClient.Command.CityObj.MilitaryGeneral)genList[i];

					}
					int ii;
				}
				catch (Exception erx)
				{
					erx = null;
				}
			}
		}

		public static Hashtable GetAllGeneral() {
            Hashtable general = new Hashtable();
            string parameter = "";
            parameter += "ltype=4";
            parameter += "&tid=";
            general = Execute(15, parameter, true);
            return general;
        }
        public static void GetMaxNhiemVu() 
		{
            Hashtable nhiemvu = new Hashtable();
            string parameter = "";
            nhiemvu = Execute(3, parameter, true);
            ArrayList task = (ArrayList)nhiemvu["task"];
            CommonObj.ThaoPhat.AllNhiemVu = new LVClient.Command.CommonObj.ThaoPhat[task.Count];
			ArrayList onetask;
			for (int i = 0; i < task.Count; i++) {
                onetask = (ArrayList)task[i];
                CommonObj.ThaoPhat.AllNhiemVu[i] = new LVClient.Command.CommonObj.ThaoPhat(int.Parse(onetask[0].ToString()), onetask[1].ToString());
            }
        }
        public static int MoveDT(int x, int y,int id) {
            string parameter = "";
            parameter += "lDestX=" + x;
            parameter += "&lDestY=" + y;
            parameter += "&lTentID=" + id;
            Hashtable info = Execute(55, parameter, true);
            // dong bang {"ret":46,"move":0,"frozen":268,"supply":[]}
            //doi trai ok {"ret":0,"move":2,"frozen":600,"supply":[]}
            int ret = int.Parse(info["ret"].ToString());
            if (ret == 46) return 1;//dong bang
            if (ret == 0) return 0;
            return -1;//error
        }
        public static int MoveDT(int x, int y, int id, string cookies) 
		{
			try
			{
				string parameter = "";
				parameter += "lDestX=" + x;
				parameter += "&lDestY=" + y;
				parameter += "&lTentID=" + id;
				Hashtable info = Execute(55, parameter, true, cookies);
				// dong bang {"ret":46,"move":0,"frozen":268,"supply":[]}
				//doi trai ok {"ret":0,"move":2,"frozen":600,"supply":[]}
				int ret = int.Parse(info["ret"].ToString());
				if (ret == 46) return 1;//dong bang
				if (ret == 0) return 0;
				return -1;//error
			}
			catch (Exception ex)
			{
				return -1;//error
			}
        }
        public static Hashtable GetHinhAnh() {
            return Execute(73, "", true);
        }


		// get thong tin quoc kho
		public static Hashtable GetGem(int nid)
		{
			try
			{
				//http://s3.linhvuong.zooz.vn/GateWay/Common.ashx?id=2&0.6633130316506091&nid=0
				Hashtable result = Command.Common.Execute(2, "nid=" + nid, false);
				//string str = "{Table:[{gem_id:1,counts:259},{gem_id:2,counts:265},{gem_id:3,counts:84},{gem_id:6,counts:93},{gem_id:7,counts:6},{gem_id:8,counts:10},{gem_id:11,counts:8},{gem_id:12,counts:15},{gem_id:13,counts:3},{gem_id:16,counts:261},{gem_id:17,counts:196},{gem_id:21,counts:54},{gem_id:24,counts:141},{gem_id:25,counts:162},{gem_id:35,counts:6},{gem_id:50,counts:2}],ret:0,nid:0}";

				if (result == null)
					return result;

				string str = result["DATA"].ToString().Trim();
				if (!str.Contains("ret:0"))
				{
					return null;
				}


				string s1 = str.Substring(str.IndexOf("[") + 1);
				s1 = s1.Substring(0, s1.IndexOf("]"));
				string[] ar = s1.Split(new char[] { ',' }, StringSplitOptions.None);

				result.Clear();
				int i = 0;
				int key;
				string value;
				while (i < ar.Length)
				{
					key = int.Parse(ar[i].Substring(ar[i].IndexOf(":") + 1).Trim());
					i++;
					value = ar[i].Substring(ar[i].IndexOf(":") + 1).Trim();
					value = value.Substring(0, value.Length - 1);
					i++;
					result.Add(key, value);
				}

				return result;
			}
			catch (Exception ex)
			{
				return null;
			}
		}
	
        /// <summary>
        /// Test đánh thử 1 mục tiêu, chưa cử đi, chỉ test thử để lấy time
        /// </summary>
        /// <param name="DestX"></param>
        /// <param name="DestY"></param>
        /// <param name="GeneralID1">ID tướng thứ 1</param>
        /// <param name="GeneralID2">ID tướng thứ 2 (không có thì để là 0)</param>
        /// <param name="GeneralID3">ID tướng thứ 3 (không có thì để là 0)</param>
        /// <param name="type">Loại mục tiêu: 1: các loại man, thảo phạt, 14: Địa tinh (ở mỏ)</param>
        /// <returns></returns>
		public static Hashtable TestDanhMotMucTieu(int DestX, int DestY	, int GeneralID1, int GeneralID2, int GeneralID3, int type)
		{

			string para;
            para = "strDestName=0";
            para += "&lBout=-1";
			para += "&lDestX=" + DestX;
			para += "&lDestY=" + DestY;
			para += "&lGeneralID1=" + GeneralID1;
			para += "&lGeneralID2=" + GeneralID2;
			para += "&lGeneralID3=" + GeneralID3;
			para += "&lPlusDestX=-1";
			para += "&lPlusDextY=-1";
			para += "&lPlusFuncID=0";
			para += "&lTarget1GID=0";
			para += "&lTarget2GID=0";
			para += "&lTarget3GID=0";
            para += "&lType=" + type;			//para += "&lType=1";			
			para += "&tid=0";
			return Execute(49, para, true);

		}
    }
}
