using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Collections;
using System.Threading;

namespace LVClient.LVThread
{
	public class AUTOVANCHUYENVK : LVClient.LVThread.ThreadSkeleton  
	{
		public ArrayList Data;
		public AUTOVANCHUYENVK(Label lbl) 
		{
            Message = lbl;
        }
		public void GetParameter(ArrayList data, int sleep)
		{
			this.Sleep = sleep;
			this.Data = data;
		}

		public override void run()
		{
			IsRun = true;

			while (true)
			{
				if (Data == null || Data.Count == 0)
				{
					SetText("Chẳng có gì để chạy cả");
					break;
				}

				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "VCVK_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue;
				SetText("Đang ngủ " + Sleep / (1000 * 60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				if (MainProcessResult > 1000000)
				{
					SetText("Bị khóa đến " + DateTime.Now.AddSeconds(MainProcessResult - 1000000).ToString("HH:mm:ss")
						+ ". Đang ngủ " + Sleep / (1000 * 60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				}
				Thread.Sleep(Sleep);

			}
		}

		private void mainprocess()
		{
			//int amountMax = objVCVK.SoLuongChuyenMoiLan;
			int amount;
			Hashtable ret;
			string cookies;
			int citypost=0;
			int cityid = 0;
			try
			{
				Message.ForeColor = System.Drawing.Color.Red;
				SetText("Đang chạy (0%)");
				Command.CommonObj.VanChuyenVK objVCVK;
				Hashtable result;
				for (int i = 0; i < Data.Count; i++)
				{
					objVCVK = (Command.CommonObj.VanChuyenVK)Data[i];
					
					cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(objVCVK.ThanhChuyenDiID);
					if (cityid != objVCVK.ThanhChuyenDiID)
					{
						citypost = Command.City.GetCityPostByID(objVCVK.ThanhChuyenDiID);
						cityid = objVCVK.ThanhChuyenDiID;
					}
					/*
					result = Command.Build.GetMarketInfo(citypost);
					if (result != null && result["ret"].ToString() == "0")
					{
						int plus_left2 = int.Parse(result["plus_left2"].ToString());
						int plus_left = int.Parse(result["plus_left"].ToString());
						int trader = int.Parse(result["trader"].ToString());
					}
					*/


					SetText("Đang chạy " + Command.CityObj.City.AllCity[citypost].name + " (đã hoàn thành " + i + "/" + Data.Count + ".)");

					if (objVCVK.DaChuyenDuoc < objVCVK.TongSoLuongChuyen)
					{
						
						amount = objVCVK.TongSoLuongChuyen - objVCVK.DaChuyenDuoc;
						if (amount > objVCVK.SoLuongChuyenMoiLan) amount = objVCVK.SoLuongChuyenMoiLan;
						ret = Command.OPT.VanchuyenVK(objVCVK.ThanhChuyenDenID, objVCVK.LoaiVuKhiID, amount, 9, cookies);
						if (ret != null && ret["ret"].ToString() == "0")
						{
							objVCVK.DaChuyenDuoc += amount;
						}
					}
					else
					{
						Data.RemoveAt(i);
					}
				}

				//Common.common.LoadDataResultForVCVK(LVClient.frmmain.LVFRMMAIN.lstVCVKResult);
			}
			catch (Exception ex)
			{

			}
		}
	}
}
