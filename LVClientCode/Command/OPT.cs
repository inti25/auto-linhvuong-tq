using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;
using System.Net;

namespace LVClient.Command {
    public class OPT {
        public static Hashtable Execute(int command, string parameter, bool wait) 
		{
            string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;
            string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/OPT.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
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
                try 
				{
					if (response == null || response.Count == 0) return null;
                    return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
                } catch (Exception ex) 
				{
                    Hashtable temp = new Hashtable();
                    temp.Add("DATA", response["DATA"].ToString());
                    return temp;
                }
            } else 
			{
				return response;
            }
        }
        public static Hashtable Execute(int command, string parameter, bool wait, string cookies) {
            string data = parameter + "&num="+LVClient.Web.LVWeb.idimage;

                string header = "POST http://s" + LVClient.Web.LVWeb.Server + ".linhvuong.zooz.vn/GateWay/OPT.ashx?id=" + command + "&0.05861361440438828 HTTP/1.1\n";
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
                    try 
					{
						if (response != null && response["DATA"] != null)
							return (Hashtable)JSON.JSON.JsonDecode(response["DATA"].ToString());
						else
							return null;
                        
                    } catch (Exception ex) 
					{	
                        Hashtable temp = new Hashtable();
                        temp.Add("DATA", response["DATA"].ToString());
                        return temp;
                    }
                } else 
				{
                    return null;
                }
            
        }

		public static Hashtable DungMuuKeTrongChienTruong(int BattleID, int GeneralPos, int PlusFunc)
		{
			string parameter = "";

			parameter += "lBattleID=" + BattleID;
			parameter += "&lDestPosID=" + GeneralPos;
			parameter += "&lPlusFunc=" + PlusFunc;
			return Execute(70, parameter, true);

		}
        public static void SellFood(int ton,int price, int type) {
            string parameter = "";
            parameter += "countprice1=" + ton*price;
            parameter += "&res1_hidden="+(type-1);
            parameter += "&res1_jsondata={floatid:\"res1\",desc:\"Lương thực\",value:0,onchange:\"Dipan.SanGuo.Build.Market.DropDown3()\",data:[{text:\"Lương thực\",value:0},{text:\"Gỗ\",value:1},{text:\"Đá\",value:2},{text:\"Sắt\",value:3},]}";
            parameter += "&sellcount1="+ton;
            parameter += "&sellprice1="+price;
            parameter += "&tid=0";
            
            parameter += "&type1="+(type);
            Execute(49, parameter, false);
        }
        public static Hashtable SellFood(int ton,int price, int type, string cookies) {
            string parameter = "";
            parameter += "countprice1=" + ton*price;
            parameter += "&res1_hidden="+(type-1);
            parameter += "&res1_jsondata={floatid:\"res1\",desc:\"Lương thực\",value:0,onchange:\"Dipan.SanGuo.Build.Market.DropDown3()\",data:[{text:\"Lương thực\",value:0},{text:\"Gỗ\",value:1},{text:\"Đá\",value:2},{text:\"Sắt\",value:3},]}";
            parameter += "&sellcount1="+ton;
            parameter += "&sellprice1="+price;
            parameter += "&tid=0";
            
            parameter += "&type1="+(type);
            return Execute(49, parameter, true, cookies);
        }
        public static int AvgPrice(int type) 
		{
            string parameter = "";
            parameter += "type=" + type;
            
            Hashtable a = Execute(29, parameter, true);
            return int.Parse(a["DATA"].ToString());
        }

		public static int GetMinPriceResource(int type, string cookies)
		{
			try
			{
				Hashtable market = Command.Common.GetMarketSeller(type, cookies);
				if (market == null)
				{
					return -1;
				}

				ArrayList infos = (ArrayList)market["infos"];
				if (infos == null || infos.Count == 0)
				{
					return -1; ;
				}

				Hashtable infoitem = (Hashtable)infos[0];	  // laays gia dau tien
				if (infoitem == null || infoitem["price"] == null)
				{
					return -1;
				}

				return int.Parse(infoitem["price"].ToString());
			}
			catch (Exception ex)
			{
				return -1;
			}
			
		}

        public static void BuyRes(int ton, int price, int seqno, int seller, int type, int buyincount, int buyinprice) {
            string parameter = "";
            parameter += "buyincount=" + buyincount;
            parameter += "&buyinprice=" + buyinprice;
            parameter += "&res_jsondata={floatid:\"res1\",desc:\"Lương thực\",value:0,onchange:\"Dipan.SanGuo.Build.Market.DropDown3()\",data:[{text:\"Lương thực\",value:0},{text:\"Gỗ\",value:1},{text:\"Đá\",value:2},{text:\"Sắt\",value:3},]}";
            parameter += "&count="+ton;
            parameter += "&countprice="+price;
            parameter += "&res_hidden="+(type-1);
            parameter += "&seller=" + seller;
            parameter += "&seqno=" + seqno;
            parameter += "&tid=0";
            
            parameter += "&type3="+(type);
            Execute(9, parameter, false);
        }
        public static void BuyRes(int ton, int price, int seqno, int seller, int type, int buyincount, int buyinprice,string cookies) 
		{
            string parameter = "";
            parameter += "buyincount=" + buyincount;
            parameter += "&buyinprice=" + buyinprice;
            parameter += "&res_jsondata={floatid:\"res1\",desc:\"Lương thực\",value:0,onchange:\"Dipan.SanGuo.Build.Market.DropDown3()\",data:[{text:\"Lương thực\",value:0},{text:\"Gỗ\",value:1},{text:\"Đá\",value:2},{text:\"Sắt\",value:3},]}";
            parameter += "&count=" + ton;
            parameter += "&countprice=" + price;
            parameter += "&res_hidden=" + (type - 1);
            parameter += "&seller=" + seller;
            parameter += "&seqno=" + seqno;
            parameter += "&tid=0";
            
            parameter += "&type3=" + (type);
            Execute(9, parameter, false, cookies);
        }


		public static void BuyRes(int restype, double buyamount, ref long gold, string cookies)
		{
			{
				int repeat = 0;
				Hashtable market = null;
				do
				{
                    try
                    {
                        market = Command.Common.GetMarketSeller(restype, cookies);
                    }
                    catch (Exception ex) { }
                    
                    repeat++;
				} while (market == null & repeat < 5);

                if (market == null) return;

				ArrayList infos = (ArrayList)market["infos"];
				//int resbuy = (int)System.Math.Floor((double)(90 * store / 100 - int.Parse(res[0].ToString())) / 1000);
				int resbuy = (int)System.Math.Ceiling((buyamount / 1000));

				Hashtable infoitem;
				if (resbuy > 0)
				{
					//duyet cho den khi het mang
					for (int j = 0; j < infos.Count; j++)
					{
						infoitem = (Hashtable)infos[j];
						int price = int.Parse(infoitem["price"].ToString());
						int count = int.Parse(infoitem["count"].ToString());
						int seller = int.Parse(infoitem["seller"].ToString());
						int seqno = int.Parse(infoitem["seqno"].ToString());

						//neu mua het luon
						if (gold - count * price >= 0)
						{
							if (resbuy - count >= 0)
							{
								Command.OPT.BuyRes(count, price, seqno, seller, 1, count, price, cookies);
								resbuy -= count;
								gold -= count * price;
							}
							else
							{
								Command.OPT.BuyRes(resbuy, price, seqno, seller, 1, count, price, cookies);
								gold -= resbuy * price;
								resbuy = 0;
							}
						}
						else if (gold - resbuy * price >= 0)
						{
							if (resbuy - count >= 0)
							{
								Command.OPT.BuyRes(count, price, seqno, seller, 1, count, price, cookies);
								resbuy -= count;
								gold -= count * price;
							}
							else
							{
								Command.OPT.BuyRes(resbuy, price, seqno, seller, 1, count, price, cookies);
								gold -= resbuy * price;
								resbuy = 0;
							}
							resbuy -= count;
						}
						if (resbuy <= 0) break;
					}
				}
			}
		}

        public static Hashtable Build(int pid, int gid, int tid) {
            string parameter = "";
            parameter += "gid=" + gid;
            parameter += "&pid=" + pid;
            parameter += "&tid=" + tid;
            
            parameter += "&type=1";
            return Execute(65, parameter, true);
        }
        public static Hashtable Build(int pid, int gid, int tid, string cookies) {
            string parameter = "";
            parameter += "gid=" + gid;
            parameter += "&pid=" + pid;
            parameter += "&tid=" + tid;
            
            parameter += "&type=1";
            return Execute(65, parameter, true, cookies);
			//retun ref:90 ok
        }
        public static Hashtable Build(int pid, int gid, int tid,int type, string cookies) {
            string parameter = "";
            parameter += "gid=" + gid;
            parameter += "&pid=" + pid;
            parameter += "&tid=" + tid;

            parameter += "&type=" + type;
            return Execute(65, parameter, true, cookies);
        }
		
		public static void ChangeBattleArray(int generalid, int arrayid)
		{
			try
			{
				Hashtable generalmilitary = Common.GetGeneralMilitary(generalid);
				//"battle_array":1,"ratio_attack":100,"ratio_PK":0,"ratio_stratagem":0,"withdraw_loss":0,"withdraw_morale":0
				string parameter = "";
				parameter += "lBattleArray=" + arrayid;
				parameter += "&lGeneralID=" + generalid;
				parameter += "&lRatioAttack=" + generalmilitary["ratio_attack"];
				parameter += "&lRatioPK=" + generalmilitary["ratio_PK"];
				parameter += "&lRatioStra=" + generalmilitary["ratio_stratagem"];
				parameter += "&lWithdrawLoss=" + generalmilitary["withdraw_loss"];
				parameter += "&lWithdrawMorale=" + generalmilitary["withdraw_morale"];
				Execute(57, parameter, false);
			}
			catch (Exception ex)
			{
			}
		}


		public static void ChangeGeneralMilitaryAttribute(int generalid, int arrayid)
		{
			try
			{
				Hashtable generalmilitary = Common.GetGeneralMilitary(generalid);
				//"battle_array":1,"ratio_attack":100,"ratio_PK":0,"ratio_stratagem":0,"withdraw_loss":0,"withdraw_morale":0
				string parameter = "";
				parameter += "lBattleArray=" + arrayid;
				parameter += "&lGeneralID=" + generalid;
				parameter += "&lRatioAttack=" + generalmilitary["ratio_attack"];
				parameter += "&lRatioPK=" + generalmilitary["ratio_PK"];
				parameter += "&lRatioStra=" + generalmilitary["ratio_stratagem"];
				parameter += "&lWithdrawLoss=" + generalmilitary["withdraw_loss"];
				parameter += "&lWithdrawMorale=" + generalmilitary["withdraw_morale"];
				Execute(57, parameter, false);
			}
			catch (Exception ex)
			{
			}
		}

		public static Hashtable ChangeGeneralMilitaryAttribute(int generalid, int arrayid, int ratioAttack,	
													int ratioPK,int ratioStra, int withdrawLoss, int withdrawMorale)
		{
			string parameter = "";
			parameter += "lBattleArray=" + arrayid;
			parameter += "&lGeneralID=" + generalid;
			parameter += "&lRatioAttack=" + ratioAttack;
			parameter += "&lRatioPK=" + ratioPK;
			parameter += "&lRatioStra=" + ratioStra;
			parameter += "&lWithdrawLoss=" + withdrawLoss;
			parameter += "&lWithdrawMorale=" + withdrawMorale;
			return Execute(57, parameter, true);

		}

		public static Hashtable ChangeGeneralMilitaryAttribute(LVClient.Command.CityObj.MilitaryGeneral general, int arrayid)
		{
			return ChangeGeneralMilitaryAttribute(general.GeneralId, arrayid, general.Military.RatioAttack, general.Military.RatioPK,
										general.Military.RatioStratagem, general.Military.WithdrawLoss, general.Military.WithdrawMorale);
		}

        public static void ChangeTargetAttack(int action, int battleid, int posid, int desctposid) {
            string parameter = "";
            parameter += "action=" + action;
            parameter += "&battleid=" + battleid;
            parameter += "&destposid=" + desctposid;
            parameter += "&posid=" + posid;
            Execute(54, parameter, false);
        }
        public static OPTObj.BattleField GetBattleField(int battleid) 
		{
			try
			{
				string parameter = "";
				OPTObj.BattleField result = new LVClient.Command.OPTObj.BattleField();
				
				parameter += "battleid=" + battleid;
				int count = 0;
				Hashtable battle = null;
				do
				{
					try
					{

						battle = Execute(24, parameter, true);
					}
					catch (Exception ex)
					{
						battle = null;
					}
					
					
					count++;
					if (battle == null) System.Threading.Thread.Sleep(2 * 1000);
				}  while ((battle == null || int.Parse(battle["ret"].ToString()) != 0) && count < 5);

				if (battle == null || int.Parse(battle["ret"].ToString()) != 0) return null;

				/*
				 * {"ret":0,"site":"Quảng Tông","mapid":711027,"bout":1,"bout_left":140,"attack_total":3,"attack_wait":0
					,"defend_total":3,"defend_wait":0,"wall":[0,0,0,0,0,0],"troops":[[1,"dai ca",14928,"Tư Qúy",358486,"Prepare
					 for War",23910,4571922,3,87,0,0,6000,0,0,0,0,0,"",1],[2,"dai ca",14928,"Mộ Dung Tuấn",366395,"Prepare
					 for War",23910,4571922,2,82,0,0,3000,0,0,0,0,0,"",1],[3,"dai ca",14928,"Mộ Dung Khác",371521,"Prepare
					 for War",23910,4571922,1,50,0,0,2000,0,0,0,0,0,"",1],[11,"",0,"Sơn tặc",0,"",0,0,2,100,0,507,0,0,0,0
					,0,0,"",16],[12,"",0,"Cường đạo",0,"",0,0,3,100,0,531,0,0,0,0,0,0,"",16],[13,"",0,"Ác bá",0,"",0,0,3
					,100,0,531,0,0,0,0,0,0,"",16]],"timestamp":1233750656}
				 */


				result.Timeleft = int.Parse(battle["bout_left"].ToString());
				result.MapID = int.Parse(battle["mapid"].ToString());  

				int attack_total = int.Parse(battle["attack_total"].ToString()); // 
				int defend_total = int.Parse(battle["defend_total"].ToString());
				ArrayList troops = (ArrayList)battle["troops"];

				int my_attack_count = 0;
				int my_defend_count = 0;
				if (troops.Count > 0)
				{				  					
					result.Battleid = battleid;
					result.allattacktroops = new LVClient.Command.OPTObj.GeneralInCombat[attack_total];
					result.alldefendtroops = new LVClient.Command.OPTObj.GeneralInCombat[defend_total];
					int i = 0; int j = 0;
					for (i = 0; i < attack_total; i++)
					{
						result.allattacktroops[i] = new LVClient.Command.OPTObj.GeneralInCombat((ArrayList)troops[j]);
						if (result.allattacktroops[i].UserID == int.Parse(LVClient.Web.LVWeb.CurrentLoginInfo.uid))
							my_attack_count++;

						j++;
					}
					for (i = 0; i < defend_total; i++)
					{
						result.alldefendtroops[i] = new LVClient.Command.OPTObj.GeneralInCombat((ArrayList)troops[j]);
						if (result.alldefendtroops[i].UserID == int.Parse(LVClient.Web.LVWeb.CurrentLoginInfo.uid))
							my_defend_count++;
						
						j++;
					}

					
					
					// lưu thông tin tướng mình
					result.myattacktroops = new LVClient.Command.OPTObj.GeneralInCombat[my_attack_count];
					result.mydefendtroops = new LVClient.Command.OPTObj.GeneralInCombat[my_defend_count];

					int my_attack_troops = 0;
					int my_defend_troops = 0;
					j = 0;
					LVClient.Command.CityObj.MilitaryGeneral gTemp;
					for (i = 0; i < result.allattacktroops.Length; i++)
					{

						
						
						if (result.allattacktroops[i].UserID == int.Parse(LVClient.Web.LVWeb.CurrentLoginInfo.uid))
						{
							//Lay thong tin ve tran hinh, don dau, rut lui ...
							gTemp = Common.GetGeneralMilitaryInfo(result.allattacktroops[i].CityID, result.allattacktroops[i].GeneralId);
							if (gTemp != null && (gTemp.Military.RatioAttack + gTemp.Military.RatioPK + gTemp.Military.RatioStratagem) == 100)
							{
								result.allattacktroops[i].Military.RatioAttack = gTemp.Military.RatioAttack;
								result.allattacktroops[i].Military.RatioPK = gTemp.Military.RatioPK;
								result.allattacktroops[i].Military.RatioStratagem = gTemp.Military.RatioStratagem;
								result.allattacktroops[i].Military.WithdrawLoss = gTemp.Military.WithdrawLoss;
								result.allattacktroops[i].Military.WithdrawMorale = gTemp.Military.WithdrawMorale;
							}

							result.myattacktroops[j] = result.allattacktroops[i];
							my_attack_troops += result.allattacktroops[i].Military.SoQuanDangCo;
							
							j++;
						}

					}
					j = 0;
					for (i = 0; i < result.alldefendtroops.Length; i++)
					{
						

						if (result.alldefendtroops[i].UserID == int.Parse(LVClient.Web.LVWeb.CurrentLoginInfo.uid))
						{
							//Lay thong tin ve tran hinh, don dau, rut lui ...
							gTemp = Common.GetGeneralMilitaryInfo(result.alldefendtroops[i].CityID, result.alldefendtroops[i].GeneralId);
							if (gTemp != null && (gTemp.Military.RatioAttack + gTemp.Military.RatioPK + gTemp.Military.RatioStratagem) == 100)
							{
								result.alldefendtroops[i].Military.RatioAttack = gTemp.Military.RatioAttack;
								result.alldefendtroops[i].Military.RatioPK = gTemp.Military.RatioPK;
								result.alldefendtroops[i].Military.RatioStratagem = gTemp.Military.RatioStratagem;
								result.alldefendtroops[i].Military.WithdrawLoss = gTemp.Military.WithdrawLoss;
								result.alldefendtroops[i].Military.WithdrawMorale = gTemp.Military.WithdrawMorale;
							}

							result.mydefendtroops[j] = result.alldefendtroops[i];
							my_defend_troops += result.alldefendtroops[i].Military.SoQuanDangCo;
							j++;
						}

					}

					if (my_attack_troops > my_defend_troops)
					{
						result.PheTanCong = true;
						result.mytroops = result.myattacktroops;
						result.enemytroops = result.alldefendtroops;
					}
					else
					{
						result.PheTanCong = false;
						result.mytroops = result.mydefendtroops;
						result.enemytroops = result.allattacktroops;
					}

					return result;
				}
				else
				{
					return null;
				}
			}
			catch (Exception ex)
			{
				return null;
			}

        }
        public static void UpdateAllPrice(int newprice,int type) {
            Hashtable stock = Command.Common.GetAllSell();
            if (stock != null) {
                ArrayList data = (ArrayList)stock["infos"];
                for (int i = 0; i < data.Count; i++) {
                    /*price	140
                    seqno	326754
                    tid	0*/
                    Hashtable item = (Hashtable)data[i];
                    if (int.Parse(item["type"].ToString()) == type) {
                        string parameter;
                        parameter = "price=" + newprice;
                        parameter += "&seqno=" + item["seqno"].ToString();
                        
                        parameter += "&tid=0";
                        Execute(68, parameter, false);
                    }
                }
            }
        }
        public static void SendMessage(string mess){
            /*
            color	#ffffff
            lType	2
            message	kiểm tra thử
            */
            string parameter;
            parameter = "color=#ffffff";
            parameter += "&lType=2";
            parameter += "&message="+mess;
            Execute(7, parameter, false);
        }
        public static void BuyItem(int id) {
            string parameter;
            parameter = "count=1";
            parameter += "&id=12";
            parameter += "&lBuyType=1";
            
            parameter += "&lPrice=0";
            parameter += "&ptype=1";
            Execute(85, parameter, false);
        }
        /*public static void DanhSonTac(int id,int g1, int g2, int g3, int g4, int g5) 
		{
            string parameter;
            if (g1 > 0) {
                UpSiKhi(g1);
            }
            if (g2 > 0) {
                UpSiKhi(g2);
            }
            if (g3 > 0) {
                UpSiKhi(g3);
            }
            if (g4 > 0) {
                UpSiKhi(g4);
            }
            if (g5 > 0) {
                UpSiKhi(g5);
            }
            parameter = "general1=" + g1;
            parameter += "&general2=" + g2;
            parameter += "&general3=" + g3;
            parameter += "&general4=" + g4;
            parameter += "&general5=" + g5;
            parameter += "&taskid=" + id;
            
            parameter += "&tid=0";
            Execute(62, parameter, false);
        }
		 */ 
        public static Hashtable DanhSonTac(int id, int g1, int g2, int g3, int g4, int g5, string cookies) 
		{
            string parameter;

			/*
			if (upsk) {
                if (g1 > 0) {
                    UpSiKhi(g1,cookies);
                }
                if (g2 > 0) {
                    UpSiKhi(g2, cookies);
                }
                if (g3 > 0) {
                    UpSiKhi(g3, cookies);
                }
                if (g4 > 0) {
                    UpSiKhi(g4, cookies);
                }
                if (g5 > 0) {
                    UpSiKhi(g5, cookies);
                }
            }
			 */

            parameter = "general1=" + g1;
            parameter += "&general2=" + g2;
            parameter += "&general3=" + g3;
            parameter += "&general4=" + g4;
            parameter += "&general5=" + g5;
            parameter += "&taskid=" + id;
            
            parameter += "&tid=0";
            return Execute(62, parameter, true, cookies);
        }
        public static Hashtable Upgrade(int id) {
            string parameter="";
            parameter += "techid=" + id;
            
            parameter += "&tid=0";
            return Execute(44, parameter, true);
        }
        public static Hashtable Upgrade(int id, string cookies) 
		{
            string parameter = "";
            parameter += "techid=" + id;
            
            parameter += "&tid=0";
            return Execute(44, parameter, true, cookies);
        }
        public static Hashtable QuanPhuAnUi(int type) {
            string parameter = "";
            parameter += "lType=" + type;
            
            parameter += "&tid=0";
            return Execute(4, parameter, true);
        }
        public static Hashtable QuanPhuAnUi(int type,string cookies) {
            string parameter = "";
            parameter += "lType=" + type;
            
            parameter += "&tid=0";
            return Execute(4, parameter, true, cookies);
        }

		public static bool QuanPhuAnUi(int type,  string cookies, bool tumualuongthuc)
		{
			const int safegold = 1000000;
			int repeat = 0;
			try
			{
				do
				{
					repeat++;
					Hashtable result = QuanPhuAnUi(type, cookies);
					if (result == null) continue;
					int mainProcessResult = int.Parse(result["ret"].ToString());

					if (mainProcessResult == 0) return true;
					if (mainProcessResult == 32)	 // thieu lua
					{
						if (tumualuongthuc)
						{						
							Hashtable citysimple = Command.City.GetCitySimpleInfo(cookies);
							ArrayList arTemp = (ArrayList)citysimple["money"];
							long gold = int.Parse(arTemp[0].ToString());					// vang hien co
							if (gold <= safegold) return false;				// không đủ vàng, đành thôi vậy
							gold = gold - safegold;
							arTemp = (ArrayList)citysimple["population"];
							int population = int.Parse(arTemp[0].ToString());
							int needfood = population * 10;
							Hashtable ResHave = Command.City.GetCurentResourceInCity(cookies);
							int maxkho = int.Parse(ResHave["MAXKHO"].ToString());
							int haveValue = int.Parse(ResHave["LUA"].ToString());

							if (needfood > maxkho) return false; 			// không đủ kho
							needfood = needfood - haveValue;
							if (needfood <= 0) continue;			// vẫn còn đủ lúa

							Command.OPT.BuyRes(LVClient.Common.Constant.RESOURCETYPE.LUA, (double)needfood, ref gold, cookies);
							//continue;
						}
					}

				} while (repeat < 3);

				return false;
			}
			catch (Exception ex)
			{
				return false;
			}
		}

        public static void Vanchuyen(int iddesc, int food, int wood, int iron, int stone,int money) {
            string parameter = "";
            parameter += "Food=" + food;
            parameter += "&Iron=" + iron;
            
            parameter += "&Money=" + money;
            parameter += "&Stone=" + stone;
            parameter += "&Wood="+wood;
            parameter += "&dest=" + iddesc;
            parameter += "&gamount=0";
            parameter += "&gid=0";
            parameter += "&tid=0";
            parameter += "&times=1";
            Execute(52, parameter, false);
        }
        public static void Vanchuyen(int iddesc, int food, int wood, int iron, int stone, int money, string cookies) 
		{
            string parameter = "";
            parameter += "Food=" + food;
            parameter += "&Iron=" + iron;
            
            parameter += "&Money=" + money;
            parameter += "&Stone=" + stone;
            parameter += "&Wood=" + wood;
            parameter += "&dest=" + iddesc;
            parameter += "&gamount=0";
            parameter += "&gid=0";
            parameter += "&tid=0";
            parameter += "&times=1";
            Execute(52, parameter, false, cookies);
        }
		public static Hashtable VanchuyenVK(int iddesc, int vkid, int amoramount, int solanvanchuyen, string cookies)
		{
			string parameter = "";
			parameter += "Food=0" ;
			parameter += "&Iron=0" ;
			parameter += "&Money=0" ;
			parameter += "&Stone=0";
			parameter += "&Wood=0" ;
			parameter += "&dest=" + iddesc;
			parameter += "&gamount=" + amoramount;
			parameter += "&gid=" + vkid;
			parameter += "&tid=0";
			parameter += "&times=" + solanvanchuyen;
			return Execute(52, parameter, true, cookies);
		}
		public static Hashtable Buywepon(int weponid, int count, int level, int posid) 
		{
            string parameter = "";
            parameter += "count=" + count;
            parameter += "&gid=" + weponid;
            
            parameter += "&lFaster=" + level;
            parameter += "&pos=" + posid;
            return Execute(38, parameter, true);
        }
        public static Hashtable Buywepon(int weponid, int count, int level, int posid,string cookies) 
		{
            string parameter = "";
            parameter += "count=" + count;
            parameter += "&gid=" + weponid;
            
            parameter += "&lFaster=" + level;
            parameter += "&pos=" + posid;
            return Execute(38, parameter, true, cookies);
        }
        /*public static void UpSiKhi( int gid) 
		{
            string parameter = "";
            parameter += "lAddPoint=10";
            parameter += "&lGeneralID=" + gid;
            
            parameter += "&tid=0";
            Execute(47, parameter, false);
        }
		 */ 
		public static void UpSiKhi(int cityid, int gid) 
		{
			/*
            string parameter = "";
            parameter += "lAddPoint=10";
            parameter += "&lGeneralID=" + gid;            
            parameter += "&tid=0";
            Execute(47, parameter, false, cookies);
			 */
			UpSiKhi(cityid, gid, 10);
        }
		public static void UpSiKhi(int cityid, int gid, int addsikhi) 
		{
            string parameter = "";
			int sk;
			
			// lay thong tin si khi hien tai
			//int sk = Command.Build.GetGeneralSyKhiInLuyenBinh(cityid, gid);

			//return;

			sk = Command.Common.GetGeneralSyKhiInLuyenBinh(cityid, gid);

            //generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, obj2.GeneralId);

			//LVClient.Command.CityObj.General geninfo = Command.Common.GetGeneralMilitaryInfoEx(cityid, gid);
			//if (geninfo == null) return;
			//sk = geninfo.Military.SyKhi;
			
			//tam thoi rem lai
			if (sk == -1) return;

			if (sk < 100)
			{
				if (addsikhi > (100 - sk)) addsikhi = (100 - sk);
			}
			else
			{
				return;		   // sy khi 100, khong luyen nua
			}
			  
			
			string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
            parameter += "lAddPoint="+addsikhi;
            parameter += "&lGeneralID=" + gid;

            parameter += "&tid=0";
            Execute(47, parameter, true, cookies);
            int k = 0;
        }

		/// <summary>
		/// Ban thưởng cho quan văn/võ
		/// </summary>
		/// <param name="ctyid">CityID</param>
		/// <param name="gid">General ID</param>
		/// <param name="money">Số tiền cần ban thưởng </param>
		/// <param name="cookies">cookies</param>
		/// <returns>true: thành công, false: không thành công</returns>
        public static bool BanThuong(int ctyid, int gid, int money, string cookies) 
		{
            string parameter = "";
            parameter += "lCityID=" + ctyid;
            parameter += "&lGeneralID=" + gid;
            
            parameter += "&lMoney=" + money;
            Hashtable ret = Execute(46, parameter, true, cookies);
            if (ret["ret"].ToString() == "0") {
                return true;
            }
            return false;
        }

		/// <summary>
		/// Ban Thưởng cho tất cả quan văn võ
		/// </summary>
		/// <param name="ok">Kết quả trả về, string những thằng đã được ban thưởng</param>
		/// <param name="fail">Kết quả trả về, string những thằng không được ban thưởng</param>
		public static void BanThuongAll(ref string ok, ref string fail)
		{

			Hashtable result;
			for (int id = 0; id < 2; id++)
			{
				if (id == 0)
				{
					// quan vo
					result = LVClient.Command.Common.GetAllSimpleMilitaryGeneralInfo();
				}
				else
				{
					// quan van
					result = LVClient.Command.Common.GetAllSimpleCivilGeneralInfo();

				}
				
				LVClient.Command.CityObj.General[] militaryGeneral;
				if (result != null)
					for (int i = 0; i < Command.CityObj.City.AllCity.Length; i++)
					{
						militaryGeneral =
							(LVClient.Command.CityObj.General[])result[Command.CityObj.City.AllCity[i].id];

						if (militaryGeneral == null) continue;
						for (int j = 0; j < militaryGeneral.Length; j++)
						{
							if (militaryGeneral[j].MucTrungThanh != 100)
							{
								try
								{

									if (LVClient.Command.OPT.BanThuong(militaryGeneral[j].CityID, militaryGeneral[j].GeneralId,
											militaryGeneral[j].Level * 10 * (100 - militaryGeneral[j].MucTrungThanh),
											LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(militaryGeneral[j].CityID)))
									{
										ok += militaryGeneral[j].GeneralName + ", ";
									}
									else
									{
										fail += militaryGeneral[j].GeneralName + ", ";
									}
								}
								catch (Exception ex)
								{
									fail += militaryGeneral[j].GeneralName + ", ";
								}
							} // end if (militaryGeneral[j].MucTrungThanh != 100)					

						}
					}
			}

		}

		// bien che dan cong
		public static Hashtable  UpdateSoluongDanCongLamMo(int cityid, int loaiMo, int soluong, string cookies )
		{

			string parameter = "";

			switch (loaiMo)
			{
				case LoaiMo.Go:
					parameter += "oid=1152419";
					break;
				case LoaiMo.Da:
					parameter += "oid=1166865";
					break;
				case LoaiMo.Sat:
					parameter += "oid=1185244";
					break;
				case LoaiMo.Thuc:
					parameter += "oid=1160293";
					break;
			}
		
			parameter += "&tid=" + cityid;
			parameter += "&workman=" + soluong;
			return Execute(20, parameter, true, cookies);
		}

		// bien che linh
		public static Hashtable UpdateSoluongLinh(int cityid, int generalid, int loaiquan, int soluong, string cookies)
		{

			string parameter = "";

			parameter += "lAmount=" + soluong;
			parameter += "&lGeneralID=" + generalid;
			parameter += "&lSoldierType=" + loaiquan;
			parameter += "&tid=" + cityid;
			return Execute(6, parameter, true, cookies);
		}

		// chieu mo tan binh
		public static Hashtable ChieuMoTanBinh(int cityid, int soluong, string cookies)
		{

			string parameter = "";

			parameter += "lAmount=" + soluong;
			parameter += "&tid=" + cityid;
			return Execute(41, parameter, true, cookies);
		}


        public static int DuoiTuongDi(int cityID, int genID, string pass)
        {
            // duoi tuong
            //http://s3.linhvuong.zooz.vn/GateWay/OPT.ashx?id=22&0.11780996712959085
            //lCityID=13835&pass=%40123&lGeneralID=437603
            //{"ret":0}
            try
            {
                string para = "lCityID=" + cityID;
                para += "&pass=" + pass;
                para += "&lGeneralID=" + genID;
                Hashtable ret = Execute(22, para, true);
                if (ret == null ) return -1;
                return int.Parse(ret["ret"].ToString());

               
            }
            catch (Exception ex)
            {
                return -1;
            }
        }

		/// <summary>
		/// Thiết lập quân giới cho tướng
		/// </summary>
		/// <param name="generalID">ID tướng</param>
		/// <param name="BoBinh1"></param>
		/// <param name="BoBinh2"></param>
		/// <param name="BoBinh3"></param>
		/// <param name="KyBinh1"></param>
		/// <param name="KyBinh2"></param>
		/// <param name="KyBinh3"></param>
		/// <param name="CungThu1"></param>
		/// <param name="CungThu2"></param>
		/// <param name="CungThu3"></param>
		/// <param name="Xe"></param>
		/// <param name="cookies"></param>
		/// <returns>ret = 0: ok</returns>
		public static Hashtable ChangeQuanGioi(int generalID, 
							int BoBinh1, int BoBinh2, int BoBinh3,
							int KyBinh1, int KyBinh2, int KyBinh3, 
							int CungThu1, int CungThu2, int CungThu3, 
							int Xe, string cookies)
		{

			string para = "lGeneralID=" + generalID;			
			para += "&lInfantryEID1=" + BoBinh1   ;	
			para += "&lInfantryEID2=" + BoBinh2   ;	
			para += "&lInfantryEID3=" + BoBinh3   ;	
			para += "&lCavalryEID1=" +  KyBinh1  ;	
			para += "&lCavalryEID2=" +  KyBinh2  ;	
			para += "&lCavalryEID3=" +  KyBinh3  ;	
			para += "&lBowmanEID1=" +   CungThu1;
			para += "&lBowmanEID2=" +   CungThu2 ;	
			para += "&lBowmanEID3=" +   CungThu3 ;	
			para += "&lMangonelEID=" + Xe   ;

			return Execute(56, para, true, cookies);

		}


        /// <summary>
        /// Cử quân đi đánh 1 mục tiêu nào đó
        /// </summary>
        /// <param name="DestMapID">Tọa độ mục tiêu</param>
        /// <param name="GeneralID1">ID tướng thứ nhất</param>
        /// <param name="GeneralID2">ID tướng thứ 2 (không có thì để là 0)</param>
        /// <param name="GeneralID3">ID tướng thứ 3 (không có thì để là 0)</param>
        /// <param name="type">Loại mục tiêu: 1: các loại man, thảo phạt, 14: Địa tinh (ở mỏ)</param>
        /// <returns></returns>
		public static Hashtable DanhMotMucTieu(int DestMapID, int GeneralID1, int GeneralID2, int GeneralID3,int type)
		{

			string para;

			para = "lBout=-1";
			para += "&lDestID=" + DestMapID;
			para += "&lGeneralID1=" + GeneralID1;
			para += "&lGeneralID2=" + GeneralID2;
			para += "&lGeneralID3=" + GeneralID3;
			para += "&lPlusDestID=0";
			para += "&lPlusFuncID=0";
			para += "&lTarget1GID=0";
			para += "&lTarget2GID=0";
			para += "&lTarget3GID=0";
            para += "&lType=" + type;             //para +="&lType=1";
			para += "&tid=0";
			return Execute(53, para, true);

		}


		public  struct LoaiMo
		{
			public const int Thuc = 0;
			public const int Go = 1;
			public const int Da = 2;
			public const int Sat = 3;

		}
		public  struct LoaiQuan
		{
			public const int Bobinh = 1;
			public const int Kybinh = 2;
			public const int Cungthu = 3;
			public const int Xe = 4;

		}
    }
}



/*


{"ret":0,"list":[[10718,"iwunu7(Đô thành)",255,-231,[[202784,"*Mộ Dung Hoàng","*Mộ Dung Hoàng",2,0,0,171,100,2140,2140,369,381,235,1710,5],[303217,"*Triệt Lý Cát","*Triệt Lý Cát",2,0,0,177,100,2180,2180,478,220,431,1770,1],[405710,"Âu Văn Mỹ","",2,0,0,49,100,590,590,79,80,87,490,0],[405714,"La Phòng","",2,0,29,64,100,740,740,30,81,85,640,0],[397975,"*Cốt Tấn","*Cốt Tấn",2,0,0,106,100,1500,1500,150,370,260,1060,4],[386274,"Trung Thành Thành","",2,0,0,57,100,670,670,78,76,14,570,0],[381228,"Giang Khôn Quán","",2,0,0,55,100,650,650,69,48,26,550,0],[381229,"Trạng Mục","",2,0,0,55,97,650,650,96,82,51,550,0],[366355,"D2A","",2,0,0,52,100,620,620,41,93,79,520,0],[367862,"Lam Mạn Tích","",2,0,0,4,100,140,140,37,25,32,40,0],[368096,"D2A","",2,0,0,37,100,470,470,30,31,71,370,0],[368100,"D2A","",2,0,0,24,100,340,340,14,29,33,240,0],[357849,"Hồng Thanh","",2,0,0,29,100,390,390,49,31,31,290,0],[357999,"4","",2,0,0,6,100,160,160,47,34,12,60,0],[358062,"41","",2,0,0,42,100,520,520,83,44,35,420,0],[358085,"30","",2,0,0,43,100,530,530,40,59,79,430,0],[358087,"28","",2,0,0,38,100,480,480,69,78,31,380,0],[277645,"Tào Chương*","Tào Chương",2,0,16,268,100,3510,3510,350,700,550,2680,5],[276392,"Khổng Lạc Diệc","",2,0,0,14,100,240,240,26,24,31,140,0],[276396,"Từ Lạc Biểu","",2,0,0,25,100,350,350,45,20,19,250,0],[276398,"Vạn Hầu Hứa Xuyên","",2,0,0,15,100,250,250,13,11,30,150,0],[276400,"Đặng Cách Quang","",2,0,0,31,100,410,410,56,22,62,310,0],[234507,"*Vưu Đột","*Vưu Đột",2,0,18,196,100,1092,2400,430,400,330,1960,19]]],[-42662,"7.1",13,-97,[[405742,"Sư Cương","",2,0,0,52,100,620,620,97,80,22,520,0]]],[-42670,"7.2",19,-94,[[412703,"Vũ Tục Nghĩa","",2,0,0,2,100,120,120,15,13,13,20,0],[412704,"Hồng Đắc","",2,0,0,3,100,130,130,10,11,10,30,0],[412999,"Thái Bạc Thúy","",2,0,0,3,100,130,130,14,14,17,30,0],

[413000,"Đạm Thai Khai Cần","",2,0,0,9,97,190,190,13,22,13,90,0],
[413427,"Tái Diệc Vân","",2,0,0,1,97,110,110,20,11,17,10,0],
[366237,"Nhược Ải Dạ","",2,0,0,40,100,500,500,65,61,13,400,0],[363818,"Bùi Trung Thúy","",2,0,0,26,100,360,360,32,59,52,260,0],[275241,"2","",2,0,0,23,100,330,330,39,52,35,230,0]]],[13139,"iwunu5",265,-229,[[405723,"Quân Lạc Xuyên","",2,0,0,47,97,570,570,44,43,68,470,0],[275162,"Thái Sử Từ*","Thái Sử Từ",2,0,24,293,100,3860,3860,560,660,580,2930,2],[426324,"Lão Nạp Thạch","",2,0,0,51,100,610,610,68,38,54,510,0],[412180,"1","",2,0,0,46,100,560,560,25,22,87,460,0],[412181,"2","",2,0,0,60,100,700,700,74,102,49,600,0],[412183,"D2A","",2,0,0,58,100,680,680,73,101,63,580,0],[405715,"D2A","",2,0,0,53,100,630,630,35,46,58,530,0],[405716,"D2A","",2,0,0,58,100,680,680,96,77,27,580,0],[405717,"D2A","",2,0,0,43,100,530,530,83,68,62,430,0],[406794,"D2A","",2,0,0,5,100,150,150,16,27,15,50,0],[406814,"D2A","",2,0,0,8,100,180,180,44,16,41,80,0],[404070,"D2A","",2,0,0,1,100,110,110,16,18,13,10,0],[404071,"D2A","",2,0,0,1,100,110,110,14,18,13,10,0],[302787,"*Nga Hà","*Nga Hà Thiếu Trượng",2,0,0,181,100,2250,2250,455,214,419,1810,0],[202618,"Quản Hợi*","Quản Hợi",2,0,0,229,100,2730,2730,610,150,600,2290,4]]],[-46538,"5.1",261,-228,[]],[-22800,"5.2",-15,-77,[[277802,"1","",2,0,0,48,100,580,580,16,13,41,480,0],[277804,"2","",2,0,0,42,100,520,520,78,53,67,420,0],[277805,"3","",2,0,0,39,97,490,490,71,54,27,390,0],[277811,"12","",2,0,0,19,100,290,290,49,22,31,190,0],[271759,"2x","",2,0,0,47,100,570,570,73,76,33,470,0],[264831,"9","",2,0,0,52,100,620,620,20,36,83,520,0]]],[-16702,"5.3",14,-93,[[412227,"Tề Hậu","",2,0,0,65,100,750,750,55,83,87,650,0],[413428,"Tấn Bối","",2,0,0,7,100,170,170,20,21,10,70,0],[413429,"Tổ Phượng Uy","",2,0,0,15,100,250,250,34,14,14,150,0],[413430,"Lộ Diêu","",2,0,0,3,100,130,130,16,17,13,30,0],[413431,"Lợi Thảo Phẩm","",2,0,0,1,100,110,110,13,20,11,10,0],[413787,"Ba Thiêm Kính","",2,0,0,7,100,170,170,12,12,21,70,0],[413788,"Tốt Chấn","",2,0,0,1,100,110,110,10,19,18,10,0]]],[-14042,"5.4",262,-227,[[404072,"Kiều Đắc Phù","",2,0,0,4,100,140,140,14,13,13,40,0],[404073,"Vạn Cần","",2,0,0,4,100,140,140,20,17,17,40,0],[400166,"Tư Bảo Chiến","",2,0,0,64,97,740,740,74,36,44,640,0],[386275,"Vân Kim","",2,0,0,57,100,670,670,22,74,46,570,0]]],[13835,"iwunu19(Đô Thành)",259,-235,[[409793,"Bạch Cảnh","",2,0,0,51,100,610,610,28,44,28,510,0],[426276,"Đào Khai","",2,0,0,17,100,270,270,50,14,36,170,0],[426277,"Dung Phong","",2,0,0,53,100,630,630,11,52,79,530,0],[426278,"Thái Đắc Hàn","",2,0,0,23,97,330,330,41,59,47,230,0],[412229,"Tốt Chiến Vĩ","",2,0,0,50,100,600,600,86,94,62,500,0],[413449,"Hạ Đạo Chiêu","",2,0,0,65,100,750,750,38,91,105,650,0],[413450,"Lư Vũ Đông","",2,0,0,64,100,740,740,94,36,29,640,0],[413451,"Chư Vũ","",2,0,0,47,100,570,570,49,81,28,470,0],[413452,"Gia Hậu Bá","",2,0,0,46,100,560,560,50,19,59,460,0],[413453,"Thám Tích","",2,0,0,3,100,130,130,40,35,24,30,0],[413454,"Lộ Lương","",2,0,0,13,100,230,230,37,13,17,130,0],[413456,"Võ Công","",2,0,0,63,100,730,730,10,18,69,630,0],[413457,"Gia Thơ","",2,0,0,35,100,450,450,69,43,14,350,0],[413458,"Vi Hùng Luân","",2,0,0,20,100,300,300,55,22,18,200,0],[406812,"Chiến Dạ","",2,0,0,6,100,160,160,39,49,10,60,0],[404201,"Quân Hiền Kim","",2,0,0,6,97,160,160,17,12,10,60,0],[404202,"Phạm Trực","",2,0,0,3,100,130,130,20,19,18,30,0],[404203,"Nguyễn Nam Lượng","",2,0,0,1,100,110,110,14,14,16,10,0],[404204,"Hứa Diệc Đấu","",2,0,0,8,100,180,180,25,10,12,80,0],[387105,"Hoàng Hải Bưu","",2,0,0,39,100,490,490,10,45,13,390,0],[363928,"Vân Phàn Thúy","",2,0,0,25,100,350,350,55,26,33,250,0],[358086,"29","",2,0,0,30,100,400,400,22,26,42,300,0],[351888,"2","",2,0,0,19,100,290,290,16,10,35,190,0],[305020,"*Việt Cát","*Việt Cát",2,0,0,181,100,2250,2250,436,236,452,1810,2],[276382,"D2A","",2,0,0,2,100,120,120,21,33,30,20,0],[276386,"7","",2,0,0,27,100,370,370,10,55,56,270,0],[276393,"Mao Yến Tĩnh","",2,0,0,26,100,360,360,37,18,35,260,0],[234480,"*Phí Sạn","*Phí Sạn",2,0,0,164,100,2080,2080,388,378,254,1640,7]]],[-46763,"19.1",-22,-72,[]],[-44431,"19.2",26,-98,[[366171,"Lỗ Khang","",2,0,0,2,97,120,120,17,24,20,20,0],[366235,"Lôi Trung Thơ","",2,0,0,57,100,670,670,35,75,55,570,0],[363823,"Tương Lưu","",2,0,0,28,97,380,380,30,46,16,280,0],[243608,"Mễ Nạp Đinh","",2,0,0,1,100,110,110,14,13,11,10,0]]],[17485,"iwunu12(Đô Thành)",265,-247,[[405188,"Quân TĩnhThất","",2,0,0,13,100,230,230,45,42,44,130,0],[405189,"Tả Tuyệt","",2,0,0,14,100,240,240,31,40,35,140,0],[405190,"Lăng Khang Thần","",2,0,0,34,100,440,440,64,22,46,340,0],[405191,"Tả Mộc Khánh","",2,0,0,24,100,340,340,39,17,54,240,0],[405192,"Song Phàn Bá","",2,0,0,20,100,300,300,54,47,24,200,0],[405193,"Không Mỹ","",2,0,0,32,100,420,420,40,38,24,320,0],[405194,"Đông Phương Trụ Bạch","",2,0,0,13,100,230,230,30,26,38,130,0],[405195,"Thần Lưu Yến","",2,0,0,42,100,520,520,51,28,24,420,0],[405196,"Tùng Trụ","",2,0,0,12,100,220,220,38,23,30,120,0],[405197,"Hạ Đắc Hậu","",2,0,0,34,100,440,440,40,55,48,340,0],[405198,"Công Dương An Thiên","",2,0,0,20,100,300,300,44,45,28,200,0],[405199,"Hà Trọng Vĩ","",2,0,0,44,100,540,540,48,34,52,440,0],[405200,"Giang Thụ","",2,0,0,35,100,450,450,50,51,55,350,0],[405244,"Chiến Tổng Quế","",2,0,0,6,100,160,160,19,20,14,60,0],[405263,"Ngụy Hiểu Hào","",2,0,0,41,100,510,510,21,65,12,410,0],[405731,"Việt Cảnh Việt","",2,0,0,23,97,330,330,31,12,25,230,0],[405732,"Diêu Đức Đông","",2,0,0,6,100,160,160,24,12,38,60,0],[405733,"Bành Đan Cốc","",2,0,0,13,97,230,230,23,31,49,130,0],[405734,"Phong Kính Khang","",2,0,0,48,100,580,580,82,19,10,480,0],[405735,"Trịnh Khởi Uy","",2,0,0,14,100,240,240,29,28,54,140,0],[405736,"Tái Uy Thơ","",2,0,0,8,100,180,180,22,11,34,80,0],[405737,"Quách Tú Hảo","",2,0,0,14,100,240,240,39,53,19,140,0],[406798,"Ngư Bảo","",2,0,0,58,100,680,680,65,21,28,580,0],[406799,"Thành Hiểu Phàn","",2,0,0,63,100,730,730,44,74,20,630,0],[406800,"Lăng Qúy Hảo","",2,0,0,25,97,350,350,26,67,37,250,0],[406801,"Tôn Dịch Lạc","",2,0,0,13,100,230,230,47,24,33,130,0],[406802,"Kỷ Hạnh","",2,0,0,41,100,510,510,69,54,45,410,0],[406803,"Hoàng Khai Quế","",2,0,0,65,100,750,750,110,57,18,650,0],[406804,"Hoàn Kính","",2,0,0,30,100,400,400,62,57,27,300,0]]],[19357,"iwunu10(Đô Thành)",254,-227,[[167931,"*Đạp Đốn","*Đạp Đốn",2,0,0,151,100,1940,1940,306,406,213,1510,5],[405719,"Cung Đẳng Quảng","",2,0,0,47,100,570,570,41,43,21,470,0],[405720,"Ngụy Quế An","",2,0,0,21,100,310,310,63,61,57,210,0],[405721,"Quách Thực Đinh","",2,0,0,43,100,530,530,33,68,45,430,0],[405722,"Cung Quế Thành","",2,0,0,21,100,310,310,25,17,54,210,0],[405725,"Lão Tử Hậu","",2,0,0,8,100,180,180,17,51,34,80,0],[405726,"Vi Minh Trạch","",2,0,0,28,100,380,380,49,28,62,280,0],[405727,"Tô Tịch Huyên","",2,0,0,34,100,440,440,28,66,20,340,0],[405728,"Tòng Dư","",2,0,0,60,100,700,700,37,12,31,600,0]]],[20118,"iwunu11(Đô Thành)",265,-219,[]],[22604,"iwunu1(Đô Thành)",261,-230,[[405711,"Mục Niên","",2,0,0,3,100,130,130,29,46,23,30,3],[405712,"Gia Cát Yến Bưu","",2,0,0,51,100,610,610,75,19,51,510,0],[405724,"Lăng Dị","",2,0,0,42,100,520,520,74,72,17,420,0],[405740,"Mạnh Nguyên Du","",2,0,0,3,100,130,130,48,39,28,30,0],[405741,"Phàn Kiện Bột","",2,0,0,10,100,200,200,38,25,31,100,0],[405743,"Ưng Nguyên","",2,0,0,15,100,250,250,30,17,58,150,0],[405745,"Triều Đơn Linh","",2,0,0,43,100,530,530,20,46,83,430,0],[405746,"Văn Nê Mai","",2,0,0,27,100,370,370,42,69,29,270,0],[387106,"Dương Tường Văn","",2,0,0,36,100,460,460,11,40,76,360,0],[276390,"Thúy Văn","",2,0,0,32,100,420,420,24,39,30,320,0]]],[22881,"iwunu20(Đô Thành)",279,-255,[[437599,"Công Thực","",2,0,0,58,100,680,680,14,65,49,580,0],[437600,"Triều Đoan","",2,0,0,55,100,650,650,76,66,35,550,0],[437601,"Tào Nạp","",2,0,0,56,100,660,660,57,18,22,560,0],[437602,"Hoa Lộ Bạch","",2,0,0,57,100,670,670,47,90,89,570,0],[437603,"Việt Diệp Quang","",2,0,0,31,100,410,410,23,17,72,310,0],[437604,"Mạnh Tú Cách","",2,0,0,34,100,440,440,20,40,28,340,0],[437605,"Vệ Thạch Xuyên","",2,0,0,33,100,430,430,66,31,51,330,0],[405678,"Ấn Hinh Vân","",2,0,0,20,100,300,300,13,10,16,200,0],[405679,"Hữu Tường Nhã","",2,0,0,36,100,460,460,24,18,15,360,0],[405680,"Ngư Côn Bưu","",2,0,0,43,97,530,530,80,16,71,430,0],[405682,"Hoài Đấu Hải","",2,0,0,18,97,280,280,15,47,18,180,0],[405683,"Ô Ải","",2,0,0,6,100,160,160,28,37,26,60,0],[405685,"Hoàn Trạch Biên","",2,0,0,19,100,290,290,20,49,11,190,0],[405686,"Quế Du","",2,0,0,42,100,520,520,12,43,67,420,0],[405687,"Công Dương Định","",2,0,0,52,100,620,620,91,59,41,520,0],[405688,"Lưu Thạc Quy","",2,0,0,52,97,620,620,82,61,46,520,0],[405690,"Lục Cần Luân","",2,0,0,11,100,210,210,37,24,41,110,0],[405691,"Long Cần Nam","",2,0,0,21,100,310,310,10,44,28,210,0],[405692,"Sở Phục Mộc","",2,0,0,8,100,180,180,32,35,27,80,0],[405693,"Du Thụ Phú","",2,0,0,46,100,560,560,21,47,85,460,0],[405694,"Tốt Vân Thiên","",2,0,0,15,100,250,250,37,46,17,150,0],[405695,"Thịnh Mỹ Đinh","",2,0,0,44,100,540,540,66,39,69,440,0],[405696,"Lữ Thơ Bản","",2,0,0,8,97,180,180,42,31,34,80,0],[405697,"Hồng Xuyên Triển","",2,0,0,17,100,270,270,37,41,23,170,0],[405699,"Tốt Trọng Trụ","",2,0,0,4,100,140,140,29,29,33,40,0],[405700,"Dũng Bột Ức","",2,0,0,39,100,490,490,55,33,77,390,0],[405701,"Giang Du Đắc","",2,0,0,2,100,120,120,40,20,28,20,0],[405703,"Hàn Trạch Hinh","",2,0,0,50,100,600,600,18,39,39,500,0],[405704,"Nhiệm Hòa Linh","",2,0,0,1,100,110,110,29,10,36,10,0],[405706,"Vũ Thiên","",2,0,0,21,100,310,310,37,26,17,210,0],[405707,"Nguyên Hải","",2,0,0,27,100,370,370,27,63,22,270,0]]],[23381,"iwunu2(Đô Thành)",268,-247,[[407968,"Tống Diêm","",2,0,0,53,100,630,630,19,84,51,530,0],[407971,"Khúc Bá An","",2,0,0,52,100,620,620,94,92,56,520,0],[407973,"Nam Cung Văn","",2,0,0,59,100,690,690,20,73,61,590,0],[405273,"Châu Hưng Quy","",2,0,0,4,100,140,140,18,11,19,40,0],[405274,"Ấn Dư","",2,0,0,6,100,160,160,17,18,15,60,0],[405275,"Hà Nê Diêu","",2,0,0,2,100,120,120,16,17,14,20,0],[405276,"Tương Du Hải","",2,0,0,1,100,110,110,15,16,12,10,0],[405277,"La Khang Ban","",2,0,0,6,100,160,160,23,18,16,60,0],[405278,"Triều Phong Cách","",2,0,0,7,100,170,170,13,20,10,70,0],[405279,"Phó Thành Vũ","",2,0,0,8,100,180,180,23,22,23,80,0],[405280,"Liễu Kính Sơn","",2,0,0,5,100,150,150,15,19,10,50,0],[405281,"Cung Thành Tử","",2,0,0,3,100,130,130,20,18,17,30,0],[405282,"Vân Phàn","",2,0,0,5,100,150,150,15,12,13,50,0],[405283,"Minh Tường Hinh","",2,0,0,1,100,110,110,15,12,18,10,0]]],[-6265,"2. Thuc 4x4",-6,-81,[[368101,"D2A","",2,0,0,27,100,370,370,25,14,11,270,0],[368102,"D2A","",2,0,0,42,100,520,520,41,34,34,420,0]]],[-4473,"2 Sat 3x3",-14,-77,[]],[28200,"iwunu13(Đô Thành)",270,-264,[[437486,"Âm Thảo Mục","",2,0,0,44,100,540,540,81,42,52,440,0],[437487,"Phạm Khôn Bạch","",2,0,0,59,100,690,690,76,86,100,590,0],[437488,"Kim Ban","",2,0,0,63,97,730,730,24,90,51,630,0],[437489,"Kim Tường","",2,0,0,50,100,600,600,15,94,62,500,0],[437490,"Từ Đẳng Cách","",2,0,0,24,100,340,340,61,12,25,240,0],[437491,"Quân Cô Minh","",2,0,0,27,100,370,370,31,10,57,270,0],[437492,"Lăng Đinh Trạch","",2,0,0,24,100,340,340,42,37,17,240,0],[405311,"Phạm Ninh Minh","",2,0,0,3,100,130,130,30,21,37,30,0],[405312,"Chiến Nê Bạch","",2,0,0,25,100,350,350,11,36,55,250,0],[405314,"Hoàng Cảnh Luân","",2,0,0,24,100,340,340,46,41,10,240,0],[405317,"Ngọ Biên Thúy","",2,0,0,5,100,150,150,12,12,12,50,0],[405318,"Quân Lượng Hoài","",2,0,0,23,100,330,330,29,22,11,230,0],[405319,"Phạm Nhẫn Lộ","",2,0,0,1,100,110,110,23,19,29,10,0],[405851," Khang Lục Tuyệt","",2,0,0,7,100,170,170,41,32,31,70,0],[405852,"Hòa Bá Phú","",2,0,0,59,100,690,690,96,18,62,590,0],[405853,"Long Tuyệt Nam","",2,0,0,4,100,140,140,21,21,41,40,0],[405854,"Lư Kì Trạch","",2,0,0,8,100,180,180,35,41,45,80,0],[405855,"Lâm Trùng Lộ","",2,0,0,29,100,390,390,59,29,48,290,0],[405856,"Sư Vân Binh","",2,0,0,39,100,490,490,26,39,33,390,0],[405857,"Quách Quảng Long","",2,0,0,3,100,130,130,13,24,32,30,0],[405858,"Nguyên Hòa Quảng","",2,0,0,15,100,250,250,50,29,18,150,0],[405859,"Điền Pháp","",2,0,0,4,97,140,140,16,39,43,40,0],[405860,"Tịnh Tuyền Hiệp","",2,0,0,50,100,600,600,69,46,64,500,0],[405861,"Sử Phù Vũ","",2,0,0,55,100,650,650,45,75,40,550,0],[405862,"Long Niên","",2,0,0,21,97,310,310,23,62,60,210,0],[405863,"Dịch Cách Ải","",2,0,0,29,100,390,390,15,13,40,290,0],[407009,"Na Nguyên Hoàng","",2,0,0,55,100,650,650,19,51,66,550,0],[367852,"Hạ Hầu Hậu","",2,0,0,7,100,170,170,39,15,24,70,0],[367853,"Nam Cung Hồng Tây","",2,0,0,21,100,310,310,13,26,46,210,0],[367854,"Tư Hào Công","",2,0,0,32,100,420,420,25,37,10,320,0],[367855,"Bàng Đoan","",2,0,0,2,100,120,120,28,30,36,20,0],[367856,"Đào Tây Trạch","",2,0,0,25,100,350,350,18,35,48,250,0],[367857,"Thu Xuân Lâm","",2,0,0,43,100,530,530,65,64,60,430,0]]],[34254,"iwunu3(Đô Thành)",268,-244,[[408129,"Hoàng Việt","",2,0,0,4,97,140,140,43,37,27,40,0],[408130,"Long Hiểu Bích","",2,0,0,37,100,470,470,74,26,58,370,0],[408131,"Hạ Hầu Luân Viên","",2,0,0,36,100,460,460,79,23,38,360,0],[408132,"Hạ Hải Quảng","",2,0,0,58,100,680,680,21,66,61,580,0],[408133,"Ưng Bản Diệp","",2,0,0,33,100,430,430,72,75,29,330,0],[408134,"Hoài Thất","",2,0,0,46,100,560,560,89,32,58,460,0],[408135,"Du Kiến","",2,0,0,24,97,340,340,37,37,10,240,0],[408136,"Bàng Diệc Phòng","",2,0,0,52,100,620,620,71,82,73,520,0],[408137,"Gia Lương","",2,0,0,30,100,400,400,57,21,70,300,0],[408138,"Âm Phương Kiệm","",2,0,0,54,100,640,640,88,25,51,540,0],[408139,"Tào Ức Hương","",2,0,0,15,100,250,250,42,46,52,150,0],[408140,"Triệu Trung Quy","",2,0,0,53,100,630,630,66,10,30,530,0],[408141,"Bàng Niên Mục","",2,0,0,24,100,340,340,16,21,35,240,0],[408142,"Liêm Phàn Phòng","",2,0,0,16,100,260,260,27,33,55,160,0],[408143,"Đạm Thai Quán Phòng","",2,0,0,22,100,320,320,30,41,36,220,0],[408144,"Khả Hoài CamCác","",2,0,0,63,100,730,730,40,34,58,630,0],[408145,"Thi Bố","",2,0,0,41,100,510,510,50,36,83,410,0],[408146,"Trang Phượng","",2,0,0,16,100,260,260,22,57,39,160,0],[408147,"Giản Quế Tây","",2,0,0,42,100,520,520,76,29,73,420,0],[408148,"Khúc Qúy","",2,0,0,1,100,110,110,40,17,10,10,0],[408300,"Ngư Dị Mạn","",2,0,0,4,100,140,140,32,21,15,40,0],[405285,"Tịnh Cảnh Quảng","",2,0,0,7,100,170,170,16,26,11,70,0],[405286,"Mạnh An Trụ","",2,0,0,4,100,140,140,25,15,16,40,0],[405287,"Lâm Trạch Mộc","",2,0,0,9,100,190,190,19,16,16,90,0],[405288,"Mạnh Nạp Kính","",2,0,0,6,100,160,160,26,18,18,60,0],[405289,"Thành Hảo Trực","",2,0,0,8,100,180,180,22,31,20,80,0],[405290,"Hoa Kị","",2,0,0,9,100,190,190,17,18,28,90,0],[405291,"Quế Hoài Phù","",2,0,0,11,97,210,210,18,25,13,110,0],[405292,"Hứa Viên Kiếm","",2,0,0,9,100,190,190,30,18,11,90,0],[405293,"Quân An","",2,0,0,11,100,210,210,30,24,15,110,0],[405294,"Phong Khôn Biểu","",2,0,0,4,100,140,140,15,26,12,40,0]]],[39557,"iwunu14(Đô Thành)",294,-265,[[313841,"Đỗ Dự*","Đỗ Dự",2,0,16,253,100,3170,3170,700,140,700,2530,2],[469089,"Hòa Thảo","",2,0,0,65,97,750,750,98,73,39,650,0],[469090,"Trử Bảo","",2,0,0,64,100,740,740,22,12,58,640,0],[469091,"Triệu Đấu Ngũ","",2,0,0,58,100,680,680,15,40,67,580,0],[405489,"Lục Thạch Phi","",2,0,0,22,100,320,320,20,40,20,220,0],[405492,"Cổ Hinh Tĩnh","",2,0,0,1,100,110,110,40,22,26,10,0],[405497,"Quân Văn Đấu","",2,0,0,60,100,700,700,21,13,95,600,0],[405500,"Nhan Thiêm","",2,0,0,51,100,610,610,78,38,30,510,0],[405501,"Dịch Hứa","",2,0,0,14,100,240,240,47,10,49,140,0],[405503,"Phùng Tích","",2,0,0,42,100,520,520,80,60,84,420,0],[405504,"Khâu Ban Niên","",2,0,0,51,100,610,610,12,58,29,510,0],[406084,"Trương Trạch Đồ","",2,0,0,42,100,520,520,24,38,34,420,0],[406085,"Nhan Sơn Không","",2,0,0,51,100,610,610,70,15,20,510,0],[406086,"Hành Kiến Dị","",2,0,0,4,100,140,140,12,12,22,40,0],[406088,"Hạnh Đồ Quảng","",2,0,0,44,100,540,540,15,24,10,440,0],[406089,"Biên Phúc Đông","",2,0,0,51,100,610,610,17,33,53,510,0],[406146,"Mao Tuyệt","",2,0,0,18,100,280,280,28,35,47,180,0],[406147,"Mộ Dung Bản Mạo","",2,0,0,29,100,390,390,67,65,16,290,0],[406148,"Bành Trùng Thần","",2,0,0,19,100,290,290,34,13,34,190,0],[406149,"Hoa Trạch Nguyên","",2,0,0,31,100,410,410,69,14,39,310,0],[406150,"Tần Đồ Bang","",2,0,0,22,100,320,320,63,37,31,220,0],[406151,"Du Tú Dịch","",2,0,0,16,100,260,260,27,49,59,160,0],[406152,"Phạm Đinh Hậu","",2,0,0,17,100,270,270,10,22,52,170,0],[406153,"Hạ Thịnh Lực","",2,0,0,47,100,570,570,28,21,12,470,0],[406154,"Võ Côn Triển","",2,0,0,14,100,240,240,55,36,52,140,0],[406155,"Tương Đạo","",2,0,0,22,100,320,320,23,36,22,220,0],[406156,"Nghiêm Kính Định","",2,0,0,28,100,380,380,34,20,61,280,0],[406157,"Hữu Bích Uy","",2,0,0,57,100,670,670,62,45,92,570,0],[406158,"Du Việt Đấu","",2,0,0,7,100,170,170,12,40,22,70,0],[406159,"ÁiThành","",2,0,0,23,100,330,330,50,13,41,230,0],[406160,"Đường Vân Tạng","",2,0,0,8,100,180,180,14,26,10,80,0],[406161,"Gia Bột Khai","",2,0,0,46,100,560,560,68,84,52,460,0],[402264,"Sử Ao","",2,0,0,39,100,490,490,57,54,36,390,0]]],[40539,"iwunu4(Đô Thành)",258,-231,[[430080,"Tào Bích","",2,0,0,41,100,510,510,57,70,36,410,0],[430081,"Cổ Phù Lan","",2,0,0,4,100,140,140,42,17,37,40,0],[404211,"Vũ Phòng","",2,0,0,9,100,190,190,22,24,14,90,0],[400167,"Thủy Tường","",2,0,0,54,100,640,640,74,76,15,540,0],[400169,"Thủy Không Cương","",2,0,0,40,100,500,500,45,19,22,400,0],[400170,"Chi Tú Phẩm","",2,0,0,39,100,490,490,69,16,60,390,0],[400171,"Vương Trụ Đồng","",2,0,0,39,100,490,490,12,30,65,390,0],[400172,"Long Trụ Mạn","",2,0,0,42,100,520,520,75,79,85,420,0],[400173,"Lâm An Dục","",2,0,0,62,100,720,720,43,49,78,620,0],[400174,"Hứa Thạc Cần","",2,0,0,48,100,580,580,10,89,23,480,0],[400175,"Chương Xuân Hiểu","",2,0,0,38,100,480,480,31,34,83,380,0],[400176,"Phàn Bạc Phú","",2,0,0,62,100,720,720,83,75,12,620,0],[400177,"Mao Kị","",2,0,0,32,100,420,420,17,52,38,320,0],[400178,"Hạ Hầu Mạo","",2,0,0,21,100,310,310,27,35,55,210,0],[400179,"Lợi Dư Nạp","",2,0,0,15,100,250,250,58,46,17,150,0],[400180,"Nhiệm Trạch Triển","",2,0,0,24,100,340,340,43,60,51,240,0],[400181,"Phùng Dư Kiến","",2,0,0,12,100,220,220,13,46,13,120,0],[400182,"Lữ Phù","",2,0,0,4,100,140,140,29,13,31,40,0],[400183,"Toàn Hải","",2,0,0,53,100,630,630,14,67,46,530,0],[400184,"Công Nghĩa","",2,0,0,16,100,260,260,19,34,34,160,0],[400185,"Long Mỹ Nguyên","",2,0,0,60,100,700,700,26,70,86,600,0],[375025,"Phán Thạc Thất","",2,0,0,58,100,680,680,47,81,69,580,0],[365681,"D2A","",2,0,0,5,100,150,150,49,29,27,50,0],[368099,"D2A","",2,0,0,61,100,710,710,93,46,81,610,0],[350696,"Cung Cần Diêm","",2,0,0,32,100,420,420,49,56,45,320,0],[276387,"8","",2,0,0,37,100,470,470,53,12,30,370,0],[276388,"11","",2,0,0,34,100,440,440,39,24,46,340,0],[234453,"*Tổ Lang","*Tổ Lang",2,0,0,175,100,2190,2190,409,361,274,1750,6]]],[-46773,"4.1",-179,11,[]],[-42517,"4.2",28,-99,[[413785,"Ngô Diệc Bố","",2,0,0,14,100,240,240,30,31,31,140,0],[413786,"Mộ Dung Nhẫn Dục","",2,0,0,1,100,110,110,11,18,22,10,0],[404210,"Trang Thảo","",2,0,0,3,100,130,130,13,15,12,30,0],[377940,"Cát Mỹ Quang","",2,0,0,55,100,650,650,33,30,37,550,0]]],[46999,"iwunu17(Đô Thành)",273,-260,[[408220,"Thúy Luân","",2,0,0,28,100,380,380,57,57,17,280,0],[408221,"Hữu Nhẫn","",2,0,0,17,100,270,270,47,33,37,170,0],[408222,"Thúy Quảng Định","",2,0,0,30,100,400,400,28,74,20,300,0],[408223,"Mễ Khải Triển","",2,0,0,6,97,160,160,34,32,44,60,0],[408224,"Phùng Hậu Bang","",2,0,0,5,100,150,150,41,15,34,50,0],[408225,"Trịnh Thịnh Kiện","",2,0,0,36,100,460,460,55,39,15,360,0],[408226,"Mã Khang Tấn","",2,0,0,34,100,440,440,22,73,20,340,0],[408227,"Ấn Kiến","",2,0,0,48,100,580,580,26,65,78,480,0],[408228,"Triệu Đinh Đơn","",2,0,0,29,100,390,390,28,46,58,290,0],[408229,"Quân Biểu","",2,0,0,29,100,390,390,57,17,23,290,0],[408231,"Quan Thụ Cốc","",2,0,0,11,100,210,210,12,37,32,110,0],[408232,"Khả Định","",2,0,0,31,100,410,410,46,56,54,310,0],[408233,"Hứa Tục Khởi","",2,0,0,26,100,360,360,33,66,56,260,0],[408234,"Lục Tuyệt Ngũ","",2,0,0,8,100,180,180,10,34,48,80,0],[405251,"Chu Qúy Hoàng","",2,0,0,3,100,130,130,18,16,20,30,0],[405323,"Phùng Thơ Biểu","",2,0,0,8,100,180,180,31,19,18,80,0],[405324,"Từ Phù","",2,0,0,9,100,190,190,38,44,39,90,0],[405325,"La Diêm","",2,0,0,27,100,370,370,49,43,23,270,0],[405327,"Hòa Tổng","",2,0,0,11,100,210,210,33,27,41,110,0],[405328,"Tư Đồ Phú Vũ","",2,0,0,23,100,330,330,35,48,27,230,0],[405330,"Nhan Biên Trực","",2,0,0,32,100,420,420,62,39,67,320,0],[405331,"Giản Phong Thụ","",2,0,0,16,100,260,260,49,10,26,160,0],[405753,"Lữ Biên Diêu","",2,0,0,44,100,540,540,75,24,20,440,0],[405754,"Gia Định Ức","",2,0,0,3,100,130,130,43,27,37,30,0],[405755,"Thần Ức Phục","",2,0,0,19,97,290,290,30,12,33,190,0],[405756,"Song Diêm Hiền","",2,0,0,2,100,120,120,13,40,31,20,0],[405758,"Khương Pháp Cốc","",2,0,0,3,100,130,130,18,26,16,30,0],[405760,"Hoa Kính Trùng","",2,0,0,32,100,420,420,70,53,61,320,0],[365419,"Phán Kiên Kì","",2,0,0,3,100,130,130,17,28,18,30,0]]],[75587,"iwunu6(Đô Thành)",264,-238,[]],[83080,"iwunu8(Đô Thành)",265,-253,[[408265,"Công Dương Thần An","",2,0,0,65,100,750,750,32,73,54,650,0],[408267,"Song Khánh Tử","",2,0,0,43,100,530,530,21,57,37,430,0],[408268,"Phương Kiệm CamCác","",2,0,0,56,100,660,660,51,32,34,560,0],[408269,"Hạ Hầu Bảo Bố","",2,0,0,63,100,730,730,83,65,21,630,0],[408270,"Lâm Cô","",2,0,0,41,100,510,510,40,68,71,410,0],[408271,"Viên Trình Hoài","",2,0,0,46,100,560,560,46,35,57,460,0],[408272,"Châu Hào Thiên","",2,0,0,10,100,200,200,54,22,35,100,0],[408273,"Nhan Trung Mộc","",2,0,0,51,97,610,610,77,64,36,510,0],[408274,"Du Trực Cách","",2,0,0,39,100,490,490,82,25,31,390,0],[408275,"Khương Cương","",2,0,0,13,100,230,230,53,58,53,130,0],[408276,"Gia Túc Đấu","",2,0,0,14,100,240,240,46,15,47,140,0],[408277,"Cung Bá Dịch","",2,0,0,56,100,660,660,30,28,83,560,0],[408278,"Vạn Khởi","",2,0,0,27,100,370,370,24,15,55,270,0],[408279,"Song Hảo Đan","",2,0,0,49,100,590,590,65,26,45,490,0],[408280,"Kế Chiêu Túc","",2,0,0,27,100,370,370,24,34,29,270,0],[408281,"Ngọ Dục","",2,0,0,33,100,430,430,18,40,29,330,0],[408282,"Mục Nguyên Cách","",2,0,0,5,100,150,150,41,30,40,50,0],[408283,"Hán Tường Hùng","",2,0,0,42,100,520,520,24,61,11,420,0],[408284,"Đạm Thai Quy","",2,0,0,60,100,700,700,69,71,54,600,0],[405295,"Thủy Lưu","",2,0,0,1,100,110,110,10,10,12,10,0],[405296,"Huỳnh Quảng Mục","",2,0,0,7,100,170,170,23,17,12,70,0],[405297,"Na Tổng","",2,0,0,1,100,110,110,12,14,11,10,0],[405298,"Nguyên Nguyên Ban","",2,0,0,1,100,110,110,10,10,13,10,0],[405299,"Tư Đồ Tổng","",2,0,0,1,100,110,110,14,13,10,10,0],[405300,"Na Hạnh","",2,0,0,1,100,110,110,13,12,10,10,0],[405301,"Điền Tú La","",2,0,0,2,100,120,120,22,12,22,20,0],[405302,"Mạnh Dịch Diệp","",2,0,0,6,100,160,160,23,29,18,60,0],[405303,"Quốc Diệp Mục","",2,0,0,2,100,120,120,20,15,21,20,0],[405304,"Vương Tạng","",2,0,0,12,100,220,220,22,14,25,120,0],[405305,"Dũng Diêm","",2,0,0,19,100,290,290,23,40,44,190,0],[405307,"Kim Uy Tĩnh","",2,0,0,4,100,140,140,12,11,16,40,0],[405308,"Dũng Phượng Thành","",2,0,0,17,100,270,270,16,35,12,170,0],[405309,"Khuông Bối Khôn","",2,0,0,12,100,220,220,13,18,23,120,0]]],[83365,"iwunu9(Đô Thành)",252,-224,[]],[93917,"iwunu15(Đô Thành)",256,-239,[]],[93938,"iwunu16(Đô Thành)",264,-250,[[405265,"Không Thịnh An","",2,0,0,9,100,190,190,11,14,15,90,0],[405267,"Thần Ngũ","",2,0,0,4,100,140,140,11,14,22,40,0],[405268,"Hạnh Uy Trụ","",2,0,0,2,100,120,120,19,13,14,20,0],[405616,"Dũng Ban","",2,0,0,9,100,190,190,15,29,25,90,0],[405618,"Trang Bối","",2,0,0,8,100,180,180,25,18,11,80,0],[405619,"Tiền Đấu Mai","",2,0,0,4,100,140,140,25,25,30,40,0],[405621,"Phạm Bá Cách","",2,0,0,10,100,200,200,26,25,11,100,0],[405622,"Vu Bạc Đồng","",2,0,0,11,100,210,210,27,27,10,110,0],[405623,"Cát Trực Ban","",2,0,0,22,100,320,320,17,44,14,220,0],[405624,"Lăng Khải Nghiêm","",2,0,0,12,100,220,220,31,31,22,120,0],[405625,"Hạ Hầu Lan Hảo","",2,0,0,27,100,370,370,47,31,23,270,0],[405748,"Công Lương Hiểu","",2,0,0,10,100,200,200,26,10,33,100,0],[405749,"Thúy Kì Bích","",2,0,0,7,97,170,170,35,28,33,70,0],[405750,"Phùng Vũ","",2,0,0,11,100,210,210,18,40,25,110,0],[404632,"Khả Trạch Khang","",2,0,0,9,100,190,190,18,20,26,90,0],[404634,"Trung Nhẫn","",2,0,0,1,100,110,110,11,17,16,10,0],[404635,"Nhiệm Yến Kì","",2,0,0,9,100,190,190,22,25,17,90,0]]],[94703,"iwunu18(Đô Thành)",252,-232,[[408166,"Mộ Dung Hiên","",2,0,0,17,100,270,270,26,30,28,170,0],[408167,"Chiến Hùng Vân","",2,0,0,6,100,160,160,10,22,11,60,0],[408168,"Khúc Cần","",2,0,0,17,100,270,270,18,46,41,170,0],[408169,"Hành Thần Hải","",2,0,0,25,97,350,350,23,15,50,250,0],[408170,"Điền Tịch Uy","",2,0,0,7,100,170,170,26,26,30,70,0],[408171,"Minh Mỹ Đạo","",2,0,0,1,100,110,110,11,21,17,10,0],[408172,"Mã Quang Khởi","",2,0,0,19,100,290,290,46,46,31,190,0],[408173,"Tử Lộ Mạo","",2,0,0,5,97,150,150,23,21,25,50,0],[408174,"Vân Nạp Nghiêm","",2,0,0,21,100,310,310,16,31,23,210,0],[408175,"Quân Biên Thành","",2,0,0,24,100,340,340,23,44,42,240,0],[408176,"Chúc Văn Hi","",2,0,0,22,100,320,320,17,46,50,220,0],[408177,"Quân Trạch Tục","",2,0,0,29,100,390,390,11,38,53,290,0],[408178,"Hoa Thực Pháp","",2,0,0,18,100,280,280,41,39,16,180,0],[408179,"Hán Lượng Viên","",2,0,0,7,100,170,170,29,11,33,70,0],[408180,"Ngọ Nạp Hưng","",2,0,0,23,100,330,330,16,21,52,230,0],[408181,"Tử Cung Nghĩa","",2,0,0,33,100,430,430,17,40,11,330,0],[408182,"Khả Lượng","",2,0,0,28,100,380,380,50,16,36,280,0]]],[96319,"Thành mới của D2A | iwunu",268,-230,[]],[96320,"Thành mới của D2A | iwunu",266,-228,[]],[96321,"Thành mới của D2A | iwunu",264,-230,[]],[96322,"Thành mới của D2A | iwunu",267,-232,[]],[96323,"Thành mới của D2A | iwunu",264,-231,[]],[96324,"Thành mới của D2A | iwunu",265,-228,[]],[96325,"Thành mới của D2A | iwunu",269,-230,[]],[96871,"Thành mới của D2A | iwunu",268,-229,[]],[96872,"Thành mới của D2A | iwunu",269,-229,[]],[96873,"Thành mới của D2A | iwunu",269,-231,[]],[96874,"Thành mới của D2A | iwunu",267,-233,[]],[97071,"Thành mới của D2A | iwunu",262,-233,[]],[97328,"Thành mới của D2A | iwunu",263,-233,[]],[97667,"Thành mới của D2A | iwunu",263,-229,[]],[97670,"Thành mới của D2A | iwunu",261,-233,[]],[98934,"Thành mới của D2A | iwunu",254,-231,[]],[98935,"Thành mới của D2A | iwunu",254,-230,[]],[99767,"Test",253,-229,[]],[99768,"Thành mới của D2A | iwunu",253,-227,[]],[99769,"Thành mới của D2A | iwunu",252,-227,[]],[99770,"Thành mới của D2A | iwunu",251,-226,[]],[99771,"Thành mới của D2A | iwunu",253,-223,[]],[99772,"Thành mới của D2A | iwunu",252,-223,[]],[101072,"nhà vệ sinh",341,-262,[]],[101498,"iwunu21",271,-231,[]],[101502,"iwunu22",261,-239,[]],[101514,"iwunu23",261,-251,[]],[103240,"Thành mới của D2A | iwunu",264,-249,[]],[103839,"Thành mới của D2A | iwunu",267,-251,[]],[104752,"bodi",401,-386,[[413778,"Cung Định Nhẫn","",2,0,0,12,97,220,220,13,23,13,120,0],[413779,"Chương Khai Đấu","",2,0,0,1,100,110,110,19,21,16,10,0],[413780,"Nguyên Pháp Phượng","",2,0,0,13,100,230,230,30,17,29,130,0],[413781,"Hành Tiêu Đắc","",2,0,0,14,100,240,240,11,13,15,140,0],[413782,"Quân Tuyền Cô","",2,0,0,13,100,230,230,19,21,21,130,0],[413784,"Kỷ Lan Tĩnh","",2,0,0,11,100,210,210,16,19,10,110,0]]],[105059,"o noi xa lam",-615,574,[]]]}



97 can 270

cap 55 tt 97 can 1650
 * 
 * level * 10 * (100 - trung thanh)
*/