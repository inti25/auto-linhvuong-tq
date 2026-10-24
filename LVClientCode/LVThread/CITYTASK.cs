using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Data;
using System.Collections;

namespace LVClient.LVThread {
	public  class CITYTASK
	{
        public Thread InThread; public string threadID;
        public bool IsRun = false;
        public int Sleep = 60000;
        public CITYTASK()
		{
        }

		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				try
				{
					//Application.DoEvents();
					//lock (LVClient.Web.LVWeb.ispause) {
					Hashtable att;
					if (LVClient.Web.LVWeb.issendsms == true)
					{
						att = LVClient.Command.Common.GetCityAttack();
						ArrayList ctys = (ArrayList)att["infos"];
						int timeatt = 999999999;
						for (int i = 0; i < ctys.Count; i++)
						{
							//Application.DoEvents();
							ArrayList onecity = (ArrayList)ctys[i];
							ArrayList attak = (ArrayList)onecity[2];
							if (timeatt > int.Parse(attak[1].ToString()) && int.Parse(attak[1].ToString()) > 0)
							{
								timeatt = int.Parse(attak[1].ToString());
							}
						}
						if (timeatt != 999999999)
						{
							if (LVClient.Web.LVWeb.lastsmstype == -1)
							{
								if (timeatt > 60 * 30) LVClient.Web.LVWeb.lastsmstype = 1;
								if (timeatt > 60 * 5 && timeatt < 60 * 30) LVClient.Web.LVWeb.lastsmstype = 2;
								if (timeatt < 60 * 5) LVClient.Web.LVWeb.lastsmstype = 3;
							}
							else
							{
								if (timeatt > 60 * 30)
								{
									//neu chua bi danh
									if (LVClient.Web.LVWeb.lastsmstype != 1)
									{
										LVClient.Web.LVWeb.LoginMobi(
											LVClient.Web.LVWeb.smsusername, LVClient.Web.LVWeb.smspass,
											LVClient.Web.LVWeb.smsto, "Quan dich dang danh nhung con lau moi toi"
										);

										//LVClient.frmmain.LVFRMMAIN.lblmainmsg.Text= "Quan dich dang danh nhung con lau moi toi";
									}
									LVClient.Web.LVWeb.lastsmstype = 1;
								}
								if (timeatt > 60 * 5 && timeatt < 60 * 30)
								{
									if (LVClient.Web.LVWeb.lastsmstype != 2)
									{
										LVClient.Web.LVWeb.LoginMobi(
											LVClient.Web.LVWeb.smsusername, LVClient.Web.LVWeb.smspass,
											LVClient.Web.LVWeb.smsto, "Quan dich dang danh nhung con 30 phut nua moi toi"
										);
										//LVClient.frmmain.LVFRMMAIN.lblmainmsg.Text = "Quan dich dang danh nhung con 30 phut nua moi toi";
									}
									LVClient.Web.LVWeb.lastsmstype = 2;
								}
								if (timeatt < 60 * 5)
								{
									if (LVClient.Web.LVWeb.lastsmstype != 3)
									{
										LVClient.Web.LVWeb.LoginMobi(
											LVClient.Web.LVWeb.smsusername, LVClient.Web.LVWeb.smspass,
											LVClient.Web.LVWeb.smsto, "Quan dich con cach 5 phut di duong. AAAA"
										);

										//LVClient.frmmain.LVFRMMAIN.lblmainmsg.Text = "Quan dich con cach 5 phut di duong. AAAA";

									}
									LVClient.Web.LVWeb.lastsmstype = 3;
								}
							}
						}
						else
						{
							LVClient.Web.LVWeb.lastsmstype = 0;
						}
					}

					// lay thong tin moi nhat cua city va sap xep lai

					//LVClient.Command.City.UpdateAllSimpleCity();
					///for (int citypost = 0; citypost < LVClient.Command.CityObj.City.AllCity.Length; citypost++)
					//{
						//	LVClient.Command.City.UpdateAllBuilding(citypost);
						//LVClient.Command.Common.GetGeneral(citypost, false);
					//}

					/*
						foreach (LVClient.Command.CityObj.City cty in LVClient.Command.CityObj.City.AllCity) 
						{
							try {
								//Application.DoEvents();
								LVClient.Command.City.SwitchCitySlow(cty.id);
								Hashtable task = Command.City.GetCityTask(LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cty.id));
								//Hashtable attack = Command.Common.GetCityAttack(cty.id,LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cty.id));
                                
								// so luong cong tring dang xay
								int countbuild = ((ArrayList)((ArrayList)((ArrayList)task["list"])[0])[4]).Count;
                                
								
								//upgarade
								int tech = int.Parse(((ArrayList)task["tech"])[2].ToString());
                                
								// thao phat
								int task1 = int.Parse(((ArrayList)task["task"])[3].ToString());
								//int mcb = int.Parse(((ArrayList)((ArrayList)((ArrayList)attack["infos"])[0])[2])[1].ToString());
								cty.citytask = new LVClient.Command.CityObj.CityTask(countbuild, tech, task1, 0);
							} catch (Exception ex) {
								cty.citytask = new LVClient.Command.CityObj.CityTask(0, 0, 0, 0);
							}
						}
					 */

				}

				catch (Exception ex)
				{
				}
			}
		}
		public void run() 
		{
			
            IsRun = true;
			while (true)
			{
				threadID = "CITYTASK_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess); 
				Thread.Sleep(Sleep);
			}
        }
		public void Auto()
		{
			if (!IsRun)
			{
				InThread = new Thread(new ThreadStart(run));
				IsRun = true;  InThread.Start();
			}
		}
        public void Stop() {
            if (IsRun) {
                InThread.Abort();
                InThread.Join();  Common.ThreadManager.RemoveThread(threadID);
                IsRun = false;
            }
        }
    }
}
