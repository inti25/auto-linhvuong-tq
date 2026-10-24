using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;

namespace LVClient.Command {
    public class City 
	{
		private static Object CityisLock = new Object();
		private static Object BuildingisLock = new Object();
		private static Object GeneralisLock = new Object();

        public static Hashtable Execute(int command,string parameter,bool wait)
		{
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;

			data = "";

            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/City.ashx?id=" + command + "&0.05861361440438828  HTTP/1.1\n";
            header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Connection: keep-alive\n";
			header += "X-Requested-With: XMLHttpRequest\n";
			header += "X-Prototype-Version: 1.5.0\n";
			header += "Referer: http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/city?login\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
			header += "Pragma: no-cache\n";
			header += "Cache-Control: no-cache\n";
			header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
			header += "\n";
			//Hashtable response = Web.LVWeb.SendAndReceive(header + data, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, wait);
			Hashtable response = Web.LVWeb.SendAndReceive(header + data, "s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn", 80, wait);
            if (wait) 
			{

				if (response !=null && response["DATA"] != null)
					return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
				else
					return null;
            } else {
                return null;
            }
        }
        public static Hashtable Execute(int command, string parameter, bool wait, string cookies) {
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/City.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
            header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7\n";
            header += "Accept: text/javascript, text/html, application/xml, text/xml, */*\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
          //  header += "Accept-Encoding: gzip,deflate\n";
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
            if (wait) {
                try {
                    return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
                } catch (Exception ex) {
                    return null;
                }
            } else {
                return null;
            }
        }

	
		public static int GetCityPostByID(int cityid)
		{
			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
			{
				if (Command.CityObj.City.AllCity[i].id == cityid) return i;
			}
			return -1;
		}

		public static Command.CityObj.City GetCityByID(int cityid)
		{
			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
			{
				if (Command.CityObj.City.AllCity[i].id == cityid) 
					return Command.CityObj.City.AllCity[i];
			}
			return null;
		}

		/// <summary>Lấy vị trí thành (citypost) đầu tiên có chưa công trình gid</summary>
		/// <param name="gid">GID của công trình.</param>
		/// <param name="isall">True: tìm cả ở trại. False: không tìm ở trại.</param>
		/// <returns>Returns -1 nếu không thấy, nếu thấy trả về citypos.</returns>

		// ham nay tra ve city post dau tien co chua cong trinh gid, 
		// isall: true neu quet ca trai, neu khong chi quet thanh
		public static int GetCityPostByGID(int gid, bool isall)
		{
			if (Command.CityObj.City.AllCity == null)
				GetAllSimpleCity();

			if (Command.CityObj.City.AllCity == null) return -1;
			
			for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
			{
				if (!isall && Command.CityObj.City.AllCity[i].id < 0) continue;


				if (Command.CityObj.City.AllCity[i].AllBuilding == null)
					GetAllBuilding(i, true);

				if (Command.CityObj.City.AllCity[i].AllBuilding == null) continue;
				for (int j = 0; j < Command.CityObj.City.AllCity[i].AllBuilding.Length; j++)
				{
					if (gid == Command.CityObj.City.AllCity[i].AllBuilding[j].gid)
						return i;
				}
			}
			return -1;
		}

		public static Command.CityObj.MilitaryGeneral GetGeneralByID(int genaralID)
		{
			try
			{
				for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
				{
					for (int j = 0; j < Command.CityObj.City.AllCity[i].MilitaryGeneral.Length; j++)
					{
						if (genaralID == Command.CityObj.City.AllCity[i].MilitaryGeneral[j].GeneralId) return Command.CityObj.City.AllCity[i].MilitaryGeneral[j];
					}
				}
				return null;
			}
			catch (Exception ex)
			{
				return null;
			}
		}
		public static Command.CityObj.MilitaryGeneral GetGeneralByID(int citypost, int genaralID)
		{
			try
			{
					for (int j = 0; j < Command.CityObj.City.AllCity[citypost].MilitaryGeneral.Length; j++)
					{
						if (genaralID == Command.CityObj.City.AllCity[citypost].MilitaryGeneral[j].GeneralId) return Command.CityObj.City.AllCity[citypost].MilitaryGeneral[j];
					}
			
				return null;
			}
			catch (Exception ex)
			{
				return null;
			}
		}

        public static CityObj.City GetCityInfo(int id) 
		{
			try
			{
				// get all city
				Hashtable result = Execute(7, "", true);
				ArrayList infos = (ArrayList)result["infos"];
				for (int i = 0; i < infos.Count; i++)
				{
					ArrayList city = (ArrayList)infos[i];
					if (id == int.Parse(city[1].ToString()))
					{
						return new LVClient.Command.CityObj.City(int.Parse(city[1].ToString()), city[2].ToString(), int.Parse(city[4].ToString()),
                                                           int.Parse(city[5].ToString()), int.Parse(city[7].ToString()), int.Parse(city[6].ToString()));
					}
				}
				return null;
			}
			catch (Exception ex)
			{
				return null;
			}
        }
        public static Hashtable GetCityTask(string cookies) 
		{
            Hashtable r = Execute(37, "ttid=0", true, cookies);
            //{"ret":0,"list":[[25547,"Âm Phong Thực Cốt",192433,4242485,[[1,3,29,1,45632],[12,3,30,1,313803],[22,3
            //,29,1,39808]],[],[],-1]],"tech":[7,23,62765],"task":[0,"",0,0]}
            return r;
        }

        public static CityObj.City GetCityInfo(int id,string cookies) {
			// get all city
            Hashtable result = Execute(7, "", true, cookies);
            ArrayList infos = (ArrayList)result["infos"];
            for (int i = 0; i < infos.Count; i++) {
                ArrayList city = (ArrayList)infos[i];
                if (id == int.Parse(city[1].ToString())) {
                    return new LVClient.Command.CityObj.City(int.Parse(city[1].ToString()), city[2].ToString(), int.Parse(city[4].ToString()),
                                                                            int.Parse(city[5].ToString()), int.Parse(city[7].ToString()));
                }
            }
            return null;
        }
        public static Hashtable GetResource() {
            return Execute(20, "", true);
        }
        public static Hashtable GetResource(string cookies) 
		{
            return Execute(20, "", true, cookies);
        }

		public static Hashtable GetCurentResourceInCity(string cookies) 
		{
			try
			{
				Hashtable ret = GetResource(cookies);
				Hashtable Result = new Hashtable();

				Result.Add("LUA", int.Parse(((ArrayList)ret["food"])[0].ToString()));
				Result.Add("GO", int.Parse(((ArrayList)ret["wood"])[0].ToString()));
				Result.Add("DA", int.Parse(((ArrayList)ret["stone"])[0].ToString()));
				Result.Add("SAT", int.Parse(((ArrayList)ret["iron"])[0].ToString()));
				Result.Add("MAXKHO", int.Parse(ret["max_storage"].ToString()));

				ret = Command.City.GetCitySimpleInfo(cookies);
				ArrayList goldarr = (ArrayList)ret["money"];
				long gold = int.Parse(goldarr[0].ToString());
				Result.Add("GOLD", gold);
				
				return Result;	


			}
			catch (Exception ex)
			{
				return null;
			}


		}

		public static void GetAllBuilding(int citypos, bool reload)
		{
			GetAllBuilding(citypos, reload, Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Command.CityObj.City.AllCity[citypos].id));
			
		}
		public static void GetAllBuilding(int citypos, bool reload, string cookies)
		{
			lock (BuildingisLock)
			{
				try
				{
					if (!reload && Command.CityObj.City.AllCity[citypos].AllBuilding != null) return;

					int count = 0;
					Hashtable temp = null;
					do
					{
						temp = Execute(5, "", true, cookies);
						count++;
					} while (temp == null && count < 5);

					if (temp == null) return;

					ArrayList infosbuilding = (ArrayList)temp["infos"];
					//Command.CityObj.City.AllCity[citypos].AllBuilding = new LVClient.Command.CityObj.Building[infosbuilding.Count];

					LVClient.Command.CityObj.Building[] arNewBuilding = new LVClient.Command.CityObj.Building[infosbuilding.Count];

					ArrayList building;
					for (int j = 0; j < infosbuilding.Count; j++)
					{
						//System.Windows.Forms.Application.DoEvents();
						building = (ArrayList)infosbuilding[j];
						//Command.CityObj.City.AllCity[citypos].AllBuilding[j] = new LVClient.Command.CityObj.Building(int.Parse(building[0].ToString()), int.Parse(building[1].ToString()), building[2].ToString(), int.Parse(building[3].ToString()));
						arNewBuilding[j] = new LVClient.Command.CityObj.Building(int.Parse(building[0].ToString()), int.Parse(building[1].ToString()), building[2].ToString(), int.Parse(building[3].ToString()));
					}

					//Array.Sort(Command.CityObj.City.AllCity[citypos].AllBuilding);
					Array.Sort(arNewBuilding);
					Command.CityObj.City.AllCity[citypos].AllBuilding = arNewBuilding;

					int k;
				}
				catch (Exception ex)
				{
				}
			}
		}

        public static void GetAllBuilding(int citypos, string cookies) 
		{
            Hashtable temp = Execute(5, "", true, cookies);
			//System.Windows.Forms.Application.DoEvents();
			
            ArrayList infosbuilding = (ArrayList)temp["infos"];
            //Command.CityObj.City.AllCity[citypos].AllBuilding = new LVClient.Command.CityObj.Building[infosbuilding.Count];
			LVClient.Command.CityObj.Building[] newBuilding = new LVClient.Command.CityObj.Building[infosbuilding.Count];

            for (int j = 0; j < infosbuilding.Count; j++) 
			{
				//System.Windows.Forms.Application.DoEvents();
                ArrayList building = (ArrayList)infosbuilding[j];
				
                //Command.CityObj.City.AllCity[citypos].AllBuilding[j] = new LVClient.Command.CityObj.Building(int.Parse(building[0].ToString()), int.Parse(building[1].ToString()), building[2].ToString(), int.Parse(building[3].ToString()));
				newBuilding[j] = new LVClient.Command.CityObj.Building(int.Parse(building[0].ToString()), int.Parse(building[1].ToString()), building[2].ToString(), int.Parse(building[3].ToString()));
 
			}
            //Array.Sort(Command.CityObj.City.AllCity[citypos].AllBuilding);
			Array.Sort(newBuilding);
			Command.CityObj.City.AllCity[citypos].AllBuilding = newBuilding;

		}

		// cap nhat thong tin ve level cua Building, neu co building moi se add them vao
		public static void UpdateAllBuilding(int citypos) 
		{
			lock (BuildingisLock)
			{
				try
				{
					if (Command.CityObj.City.AllCity[citypos].AllBuilding == null)
					{
						GetAllBuilding(citypos, true);
						return;
					}

					Hashtable temp = Execute(5, "", true, Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Command.CityObj.City.AllCity[citypos].id));

                    try
                    {
                        int size = int.Parse(temp["size"].ToString());
                    }
                    catch (Exception ex) { }

                    ArrayList infosbuilding = (ArrayList)temp["infos"];

					Command.CityObj.Building[] newBuilding = new LVClient.Command.CityObj.Building[infosbuilding.Count];

					Command.CityObj.Building oldBuilding;
					ArrayList building;
					for (int i = 0; i < infosbuilding.Count; i++)
					{
						building = (ArrayList)infosbuilding[i];
						newBuilding[i] = new LVClient.Command.CityObj.Building(int.Parse(building[0].ToString()), int.Parse(building[1].ToString()), building[2].ToString(), int.Parse(building[3].ToString()));
						if (Command.CityObj.City.AllCity[citypos].AllBuilding != null)
						{
							// tim xem da co chua
							for (int j = 0; j < Command.CityObj.City.AllCity[citypos].AllBuilding.Length; j++)
							{
								oldBuilding = Command.CityObj.City.AllCity[citypos].AllBuilding[j];

								if (newBuilding[i].gid == oldBuilding.gid && newBuilding[i].pid == oldBuilding.pid)
								{
									newBuilding[i].isDown = oldBuilding.isDown;
									newBuilding[i].isUp = oldBuilding.isUp;

									break;
								}
							}
						}
					}

					if (newBuilding != null) Array.Sort(newBuilding);

					Command.CityObj.City.AllCity[citypos].AllBuilding = newBuilding;
					//if (Command.CityObj.City.AllCity[citypos].AllBuilding != null) Array.Sort(Command.CityObj.City.AllCity[citypos].AllBuilding);
				}
				catch (Exception ex)
				{
				}
			} //lock
		}

        public static void GetAllCity()
        {
            //{"ret":0,"infos":[[4,23910,"Prepare for War",185871,81,515,0],[2,-33311,"Prepare for Peace",162216,60
            //,533,23910],[1,63000,"Prepare for Sleep",4683,87,653,0],[2,-22087,"Đừng oánh tui",4678,82,653,63000]
            //]}
            Hashtable result = Execute(7, "", true);
            ArrayList infos = (ArrayList)result["infos"];
            Command.CityObj.City.AllCity = new LVClient.Command.CityObj.City[infos.Count];


            for (int i = 0; i < infos.Count; i++)
            {
                ArrayList city = (ArrayList)infos[i];
                // public City(int id, string name, int x, int y)
                Command.CityObj.City.AllCity[i] = new LVClient.Command.CityObj.City(int.Parse(city[1].ToString()), city[2].ToString(), 
                    int.Parse(city[4].ToString()), int.Parse(city[5].ToString()), int.Parse(city[7].ToString()));
                
                
                Command.City.SwitchCitySlow(int.Parse(city[1].ToString()));
                while (true)
                {
                    try
                    {
                        GetAllBuilding(i);
                        break;
                    }
                    catch (Exception ex)
                    {

                    }
                }
                while (true)
                {
                    try
                    {
                        // laays thong tin ve tuong trong trai/thanh
                        Command.Common.GetGeneral(i);
                        break;
                    }
                    catch (Exception ex)
                    {

                    }
                }
            }
        }


        // Lay thong tin co ban ve city
        public static void GetAllSimpleCity()
        {
            //{"ret":0,"infos":[[4,23910,"Prepare for War",185871,81,515,0],[2,-33311,"Prepare for Peace",162216,60
            //,533,23910],[1,63000,"Prepare for Sleep",4683,87,653,0],[2,-22087,"Đừng oánh tui",4678,82,653,63000]
            //]}

            int count = 0;
            Hashtable result = null;
            do
            {
                result = Execute(7, "", true);
                count++;
            } while (result == null && count < 5);

            ArrayList infos = (ArrayList)result["infos"];
            //Command.CityObj.City.AllCity = new LVClient.Command.CityObj.City[infos.Count];

            Command.CityObj.City[] newcity = new LVClient.Command.CityObj.City[infos.Count];

            ArrayList city;
            for (int i = 0; i < infos.Count; i++)
            {
                //System.Windows.Forms.Application.DoEvents();

                city = (ArrayList)infos[i];
                // public City(int id, string name, int x, int y)
                newcity[i] = new LVClient.Command.CityObj.City(int.Parse(city[1].ToString()), city[2].ToString(), int.Parse(city[4].ToString()), 
                                                                int.Parse(city[5].ToString()), int.Parse(city[7].ToString()), int.Parse(city[6].ToString()));
                


                Command.City.SwitchCitySlow(int.Parse(city[1].ToString()));
            }

            Command.CityObj.City.AllCity = newcity;
        }


		public static void UpdateAllSimpleCity()
		{
			lock (CityisLock)
			{

				if (Command.CityObj.City.AllCity == null)
				{
					GetAllSimpleCity();
					return;
				}

				//{"ret":0,"infos":[[4,23910,"Prepare for War",185871,81,515,0],[2,-33311,"Prepare for Peace",162216,60
				//,533,23910],[1,63000,"Prepare for Sleep",4683,87,653,0],[2,-22087,"Đừng oánh tui",4678,82,653,63000]
				//]}
				Hashtable result = Execute(7, "", true);
				if (result == null) return;

				ArrayList infos = (ArrayList)result["infos"];

				Command.CityObj.City[] newcity = new LVClient.Command.CityObj.City[infos.Count];
				Command.CityObj.City oldcity;

				ArrayList city;
				string newname;
				for (int i = 0; i < infos.Count; i++)
				{
					//System.Windows.Forms.Application.DoEvents();

					city = (ArrayList)infos[i];
					// public City(int id, string name, int x, int y)
					newcity[i] = new LVClient.Command.CityObj.City(int.Parse(city[1].ToString()), city[2].ToString(), int.Parse(city[4].ToString()), 
                        int.Parse(city[5].ToString()), int.Parse(city[7].ToString()), int.Parse(city[6].ToString()));
                    
                    // cap thanh
                    newcity[i].size = int.Parse(city[7].ToString());

                    oldcity = LVClient.Command.City.GetCityByID(newcity[i].id);

                    if (oldcity != null)
                    {
                        newcity[i].AllBuilding = oldcity.AllBuilding; 
                    }

					
                    //Command.City.SwitchCitySlow(int.Parse(city[1].ToString()));
					
                    /*
                    for (int j = 0; j < Command.CityObj.City.AllCity.Length; j++)
					{
						oldcity = Command.CityObj.City.AllCity[j];
						if (newcity[i].id == oldcity.id)
						{
							// thay doi moi ten, giu lai het cac thuoc tinh khac
							newname = newcity[i].name;
							newcity[i] = oldcity;
							newcity[i].name = newname;


							break;
						}
					}
                     */ 
				}

				Command.CityObj.City.AllCity = newcity;
			}
		}


		public static int GetBuildingPostById(int citypost, int gid)
		{
			Command.CityObj.Building building;

			if (Command.CityObj.City.AllCity == null) return -1;
			if (Command.CityObj.City.AllCity[citypost].AllBuilding == null)
				LVClient.Command.City.UpdateAllBuilding(citypost);

			for (int i = 0; i < Command.CityObj.City.AllCity[citypost].AllBuilding.Length; i++)
			{
				building = Command.CityObj.City.AllCity[citypost].AllBuilding[i];
				if (building.gid == gid ) return i;
			}

			return -1;


		}

		public static int GetBuildingPostById(int citypost, int gid, int pid)
		{
			Command.CityObj.Building building;

			if (Command.CityObj.City.AllCity == null) return -1;
			if (Command.CityObj.City.AllCity[citypost].AllBuilding == null) return -1;

			for (int i = 0; i < Command.CityObj.City.AllCity[citypost].AllBuilding.Length; i++)
			{
				building = Command.CityObj.City.AllCity[citypost].AllBuilding[i];
				if (building.gid == gid && building.pid == pid) return i;
			}

			return -1;

		}
		public static void GetAllBuilding(int citypos)
		{
			//hungtv add
			//Command.City.SwitchCitySlow(Command.CityObj.City.AllCity[citypos].id);
			//---
            Hashtable temp = Execute(5, "", true);
            ArrayList infosbuilding = (ArrayList)temp["infos"];
            Command.CityObj.City.AllCity[citypos].AllBuilding = new LVClient.Command.CityObj.Building[infosbuilding.Count];
            for (int j = 0; j < infosbuilding.Count; j++) {
                ArrayList building = (ArrayList)infosbuilding[j];
                Command.CityObj.City.AllCity[citypos].AllBuilding[j] = new LVClient.Command.CityObj.Building(int.Parse(building[0].ToString()), int.Parse(building[1].ToString()), building[2].ToString(), int.Parse(building[3].ToString()));
            }
            Array.Sort(Command.CityObj.City.AllCity[citypos].AllBuilding);
        }
       
        public static void SwitchCitySlow(int idcity) {
            //Execute(50, "tid=" + idcity, true);
            LVClient.Web.LVWeb.CurrentLoginInfo.cid = "" + idcity;
        }
        public static void SwitchCity(int idcity) {
            //Execute(50, "tid=" + idcity);
            lock (LVClient.Web.LVWeb.CurrentLoginInfo.cid) {
                LVClient.Web.LVWeb.CurrentLoginInfo.cid = ""+idcity;
            }
        }
        public static Hashtable GetCitySimpleInfo() {
            return Execute(6, "", true);
        }
        public static Hashtable GetCitySimpleInfo(string cookies) 
		{
            return Execute(6, "", true, cookies);
        }

		// hungtv add 
		public static LVClient.Command.CityObj.CityTask GetCityTaskByCityID(int cityid)
		{
			//int cityid = LVClient.Command.CityObj.City.AllCity[citypos].id;
				try
				{
					LVClient.Command.City.SwitchCitySlow(cityid);
					Hashtable task = Command.City.GetCityTask(LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid));
					//Hashtable attack = Command.Common.GetCityAttack(cty.id,LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cty.id));
					int countbuild = ((ArrayList)((ArrayList)((ArrayList)task["list"])[0])[4]).Count;
					int tech = int.Parse(((ArrayList)task["tech"])[2].ToString());
					int task1 = int.Parse(((ArrayList)task["task"])[3].ToString());
					//int mcb = int.Parse(((ArrayList)((ArrayList)((ArrayList)attack["infos"])[0])[2])[1].ToString());
					return (new LVClient.Command.CityObj.CityTask(countbuild, tech, task1, 0));
				}
				catch (Exception ex)
				{
					return ( new LVClient.Command.CityObj.CityTask(0, 0, 0, 0));
				}			
		}

			// hungtv add 
		public static LVClient.Command.CityObj.CityTask GetCityTaskByCityPos(int citypos)
		{
			return GetCityTaskByCityID(LVClient.Command.CityObj.City.AllCity[citypos].id);
		}
        
    }
}
