using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;
using System.Windows.Forms;
namespace LVClient.Command {
    public class Build {
        /**
         * Cấu trúc lệnh Build
         * gid = lấy từ city
         * pid = lấy từ city
         * tab = tùy
         * tid = 0
         * 
         */
        public static Hashtable Execute(int command, string parameter, bool wait) {
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/build.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
            header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7\n";
            header += "Accept: text/javascript, text/html, application/xml, text/xml, */*\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Connection: keep-alive\n";
            header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/city\n";
            header += "X-Requested-With: XMLHttpRequest\n";
            header += "X-Prototype-Version: 1.5.0\n";
            header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
            header += "Content-Type: application/x-www-form-urlencoded; charset=UTF-8\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";

            Hashtable response = Web.LVWeb.SendAndReceive(header + data, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, wait);
            if (wait) {
                return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
            } else {
                return null;
            }
        }

        public static Hashtable Execute(int command, string parameter, bool wait, string cookies) {
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/build.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
            header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7\n";
            header += "Accept: text/javascript, text/html, application/xml, text/xml, */*\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Connection: keep-alive\n";
            header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/city\n";
            header += "X-Requested-With: XMLHttpRequest\n";
            header += "X-Prototype-Version: 1.5.0\n";
            header += "Cookie: " + cookies + "\n";
            header += "Content-Type: application/x-www-form-urlencoded; charset=UTF-8\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";

            Hashtable response = Web.LVWeb.SendAndReceive(header + data, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, wait);
            if (wait) 
			{
				if (response != null && response["DATA"] != null)
					return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
				else
					return null;
            } 
			else 
			{
                return null;
            }
        }

        public static Hashtable ExecuteExp(int command, int gid, int pid, int tab, int tid) 
		{
            string parameter = "";
            parameter += "gid=" + gid;
            parameter += "&pid=" + pid;
            parameter += "&tab=" + tab;
            parameter += "&tid=" + tid;
            return Execute(command, parameter, true);
        }

        public static Hashtable GetUpgrade(int citypos) {
            Hashtable upgrade = new Hashtable();
            Command.City.SwitchCitySlow(Command.CityObj.City.AllCity[citypos].id);
            for (int i = 0; i < Command.CityObj.City.AllCity[citypos].AllBuilding.Length; i++) {
                if (Command.CityObj.City.AllCity[citypos].AllBuilding[i].name == "Đại học điện") {
                    upgrade = ExecuteExp(2, Command.CityObj.City.AllCity[citypos].AllBuilding[i].gid, Command.CityObj.City.AllCity[citypos].AllBuilding[i].pid, 1, 0);
                    break;
                }
            }
            return upgrade;
        }
        public static bool SelectBuilding(int cityid, int gid, int pid, int tab, string cookies) 
		{
            Hashtable r = Execute(2, "gid=" + gid + "&pid=-1" + "&tab="+tab+"&tid="+cityid, true, cookies);
			//Hashtable r = Execute(2, "gid=" + gid + "&pid="+ pid + "&tab=" + tab + "&tid=" + cityid, true, cookies);

			if (r["ret"].ToString() == "0") return true;
            return false;
        }

		public static Hashtable SelectBuildingInfo(int cityid, int gid, int pid, int tab, string cookies)
		{
			return Execute(2, "gid=" + gid + "&pid=-1" + "&tab=" + tab + "&tid=" + cityid, true, cookies);
			
		}

		// lay so luong cong trinh co the build
		// tra ve so luong co the buil
		public static int GetMaxNumCanBuild()
		{
			int citypostocheck = -1;
			int maxbuild = 1;

			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
			{
				if (Command.CityObj.City.AllCity[i].id >0 )
				{
					citypostocheck = i;
					break;
				}
			}
			if (citypostocheck != -1)
			{
				Command.CityObj.City city = Command.CityObj.City.AllCity[citypostocheck];
				LVClient.Command.City.SwitchCitySlow(city.id);
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(city.id);
				//checkret = Command.Build.ExecuteExp(2, 1, 8, 2, 0);


				Hashtable r = Command.Build.SelectBuildingInfo(city.id, 1, 8, 2, cookies);
				if (r != null & r["plus_left"].ToString().Trim() != "0")
					maxbuild = 3;
				else
					maxbuild = 1;
			}

			return maxbuild;
			//-----------------
							
		}
		
        public static bool SelectBuilding(int cityid, int name, string cookies) 
		{
			LVClient.Command.CityObj.City cty; 

            //foreach (LVClient.Command.CityObj.City cty in LVClient.Command.CityObj.City.AllCity) 
			for (int c=0; c < LVClient.Command.CityObj.City.AllCity.Length; c++) 
			{
				cty = LVClient.Command.CityObj.City.AllCity[c];

                if (cty.id == cityid) 
				{
					LVClient.Command.City.GetAllBuilding(c, false, LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cty.id));


                    foreach (LVClient.Command.CityObj.Building b in cty.AllBuilding) 
					{
                        if (b.gid == name) 
						{
                            int tab = 0;
                            if (SelectBuilding(cityid,b.gid, b.pid, 0, cookies)) return true;
                            for (int i = -2; i < 3; i++) 
							{
                                if (SelectBuilding(cityid,b.gid, b.pid, i, cookies)) 
								{
                                    return true;
                                };
                            }
                            
                            return false;
                        }
                    }
                }
            }
            return false;
        }

		//Lay thong tin tai nguyen can thiet de nang cap nha
		public static Hashtable getResourceNeedForUpgradeBuilding(int gid, int pid, string cookies)
		{
			try
			{
				Hashtable result = null;

				Hashtable ret = Execute(2, "gid=" + gid + "&pid=" + pid + "&tab=-1", true, cookies);
				if (ret == null) return null;
				ArrayList update = (ArrayList)ret["update"];
				result = new Hashtable();
				result.Add("LUA", int.Parse(update[5].ToString()));
				result.Add("GO", int.Parse(update[6].ToString()));
				result.Add("DA", int.Parse(update[7].ToString()));
				result.Add("SAT", int.Parse(update[8].ToString()));
				result.Add("GOLD", int.Parse(update[9].ToString()));
				result.Add("TIME", int.Parse(update[10].ToString()));



				return result;

			}
			catch (Exception ex)
			{
				return null;
			}

		}

		public static Hashtable GetMarketInfo(int citypost)
		{

			try
			{
				Hashtable result;
				int cityID = Command.CityObj.City.AllCity[citypost].id;

				LVClient.Command.City.SwitchCitySlow(cityID);
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
				// lay pid cua chợ
				int buldingpos = Command.City.GetBuildingPostById(citypost, 11);
				int pid = Command.CityObj.City.AllCity[citypost].AllBuilding[buldingpos].pid;

				bool ret = Command.Build.SelectBuilding(cityID, 11, cookies);

				//string para = "gid=11&pid=" + pid + "&tab=1&tid=" + cityID +"&ttid=" + cityID + "&cid=" + cityID;
				string para = "gid=11&pid=-1&tab=1&tid=" + cityID + "&ttid=" + cityID + "&cid=" + cityID;
				
				result = Execute(2, para, true, cookies);
				int iii;
				return result;
			}
			catch (Exception ex)
			{
				return null;
			}

		}


		/// <summary>
		/// Lấy thông tin về danh tướng viếng thăm trong quán trọ hoặc tử quán
		/// </summary>
		/// <param name="type">1: võ tướng, 2: quan văn</param>
		/// <returns>Trả về tên tướng nếu có hoặc trống nếu không có</returns>		
		// Lay thong tin tuong vieng tham
		// 1: quan vo (tuu quan)
		// 2: quan van (quan tro)
		// return : ten dnah tuong hoac ""
		public static string GetGeneralViengTham(int type)
		{
			try
			{
				int gid;
				if (type == 1)
					gid = 8;
				else
					gid = 7;

				int citypos = Command.City.GetCityPostByGID(gid, false);
				int cityid = Command.CityObj.City.AllCity[citypos].id;
				Command.City.SwitchCitySlow(cityid);
				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

				string para = "gid=" + gid + "&pid=-1&tab=2&tid=0";
				Hashtable ret = Execute(2, para, true, cookies);

				if (ret == null || ret["ret"].ToString() != "0") return "";

				ArrayList ar = (ArrayList)ret["rumor"];

				if (ar.Count <= 0) return "";

				string gen = ar[3].ToString().Trim();
				return gen;
			}
			catch (Exception ex)
			{
				return "";
			}
		}

		public static string GetGeneralViengTham()
		{
			string str = "";
			if (LVClient.frmmain.ThongBaoDanhTuongViengTham)
			{
				str = Command.Build.GetGeneralViengTham(1);
				if (str != "")
				{
					str = "Đang có danh tướng " + str + " " + LVClient.Common.DanhSachTuong.GetTuongInfo(str.Trim()) + 
						" viếng thăm trong tửu quán";
				}
				else
				{
					str = Command.Build.GetGeneralViengTham(2);
					if (str != "")
					{
						str = "Đang có danh sỹ " + str + " " + LVClient.Common.DanhSachTuong.GetTuongInfo(str.Trim()) +
							" viếng thăm trong quán trọ";
					}
				}
			}

			return str;
		}
	

	}
}
