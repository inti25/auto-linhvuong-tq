using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using LVClient.Command.CommonObj;

namespace LVClient.Command
{
	public class Map
	{
		public static Hashtable Execute(int command, string parameter, bool wait)
		{
			string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
			string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/Map.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
			header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
			header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7\n";
			header += "Accept: text/javascript, text/html, application/xml, text/xml, */*\n";
			header += "Accept-Language: en-us,en;q=0.5\n";
			//header += "Accept-Encoding: gzip,deflate\n";
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
			if (wait)
			{
				return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
			}
			else
			{
				return null;
			}
		}


		public static Hashtable Execute(int command, string parameter, bool wait, string cookies)
		{
			string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
			string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/Map.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
			header += "Host: s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn\n";
			header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7\n";
			header += "Accept: text/javascript, text/html, application/xml, text/xml, */*\n";
			header += "Accept-Language: en-us,en;q=0.5\n";
			//header += "Accept-Encoding: gzip,deflate\n";
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


		/// <summary>
		/// Tìm Man với mapID cho trước
		/// </summary>
		/// <param name="mapidcenter">Map ID</param>
		/// <param name="ret">ArrayList trả về chứa LVClient.Command.CommonObj.Npc_tentObj </param>
		public static void FindMan(long mapidcenter, ref ArrayList ret)
		{
			 try
            {
				if (ret == null) ret = new ArrayList();
				
                Hashtable hashtable = Map.Execute(6, "mid=" + mapidcenter, true);
                if (hashtable != null)
                {
                    ArrayList list = (ArrayList) hashtable["npc_tent"];
                    for (int i = 0; i < list.Count; i++)
                    {
                        ArrayList list2 = (ArrayList) list[i];
                        Npc_tentObj obj2 = new Npc_tentObj();
                        obj2.BatleId = int.Parse(list2[0].ToString());
                        obj2.ManID = int.Parse(list2[1].ToString());
                        obj2.MapID = int.Parse(list2[2].ToString());
                        
						ret.Add(obj2);
                    }
                }
            }
            catch (Exception)
            {
            }
		}


        /// <summary>
        /// Tìm Man với mapID cho trước
        /// </summary>
        /// <param name="mapidcenter">Map ID</param>
        /// <returns>Array trả về chứa LVClient.Command.CommonObj.Npc_tentObj. Null nếu ko có </returns>
        public static Npc_tentObj[] FindMan(long mapidcenter)
        {
            try
            {
                ArrayList ret = new ArrayList();
                FindMan(mapidcenter, ref ret);
                if (ret == null || ret.Count == 0) return null;

                Npc_tentObj[] result = new Npc_tentObj[ret.Count];

                for (int i = 0; i < ret.Count; i++)
                {
                    result[i] = (Npc_tentObj)ret[i];

                }

                return result;
            }
            catch (Exception)
            {
                return null;
            }
        }
    
    }
}
