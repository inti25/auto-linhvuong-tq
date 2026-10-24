using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Data;
using System.Collections;

using LVClient.Command;
using LVClient.Command.CityObj;
using LVClient.Common;
using LVClient.LVThread;
using LVClient.Web;
using LVClient.Command.CommonObj;
using System.Drawing;


namespace LVClient.LVThread
{
    public class AUTOBINHMAN : ThreadSkeleton
    {
        private Hashtable BinhManList = new Hashtable();		//BinhManList[GeneralId,  BinhManObj]
		private ArrayList arBinhManList = new ArrayList();		// chứa  BinhManObj không bị trùng, phục vụ cho  AUTOFIGHTING
        private int lastcityX = 0;
        private int lastcityY = 0;
        private int lastmapidcenter = 0;
        private ArrayList ManMap = new ArrayList();
        private const int MAPHALFSIZE = 6;
        private const int MAPSIZE = 11;
      

        public AUTOBINHMAN(Label lbl)
        {
            base.Message = lbl;
        }

		public void GetParameter(ArrayList geninfolist, int sleep)
		{

			this.Sleep = sleep;
			geninfolist.Sort();
			this.BinhManList.Clear();
			arBinhManList.Clear();
			ArrayList list = null;
			BinhManObj binhManObj =null;
			int key = 0;
			for (int i = 0; i < geninfolist.Count; i++)
			{
				binhManObj = (BinhManObj)geninfolist[i];
				if (key != binhManObj.GeneralId)
				{
					if (i != 0)
					{
						this.BinhManList.Add(key, list);
						arBinhManList.Add(binhManObj);
					}
					list = new ArrayList();
					list.Add(geninfolist[i]);
					key = binhManObj.GeneralId;
				}
				else
				{
					list.Add(geninfolist[i]);
				}
			}
			if ((list != null) && (list.Count > 0))
			{
				this.BinhManList.Add(key, list);
				arBinhManList.Add(binhManObj);
			}
		}

        /*public void GetParameter(ArrayList geninfolist, int sleep)
        {

            this.Sleep = sleep;
            geninfolist.Sort();
            this.BinhManList.Clear();
            arBinhManList.Clear();
            ArrayList list = null;
            BinhManObj binhManObj = null;
            int key = 0;
            for (int i = 0; i < geninfolist.Count; i++)
            {
                binhManObj = (BinhManObj)geninfolist[i];
                if (key != binhManObj.GeneralId)
                {
                    if (i != 0)
                    {
                        this.BinhManList.Add(key, list);
                        arBinhManList.Add(binhManObj);
                    }
                    list = new ArrayList();
                    list.Add(geninfolist[i]);
                    key = binhManObj.GeneralId;
                }
                else
                {
                    list.Add(geninfolist[i]);
                }
            }
            if ((list != null) && (list.Count > 0))
            {
                this.BinhManList.Add(key, list);
                arBinhManList.Add(binhManObj);
            }
        }
*/
       
        private void DieuTuongDiDanhDiaTinh(ArrayList geninfo)
        {
            BinhManObj binhmanobj =null;
            try
            {

                for (int man = 0; man < geninfo.Count; man++)
                {
                    binhmanobj = (BinhManObj)geninfo[man];
                    int cityID = binhmanobj.CityID;
                    LVClient.Command.CityObj.City cityByID = LVClient.Command.City.GetCityByID(cityID);
                    string cookies = LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
                    LVClient.Command.City.SwitchCitySlow(cityID);
                    SetText("Chuẩn bị tướng " + binhmanobj.GeneralName + " đánh địa tinh tọa độ (" + binhmanobj.ToaDoMoX + ", " + binhmanobj.ToaDoMoY + "...");

                    MilitaryGeneral generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, binhmanobj.GeneralId);
                    if (generalMilitaryInfoEx == null)
                    {
                        SetText("Tướng " + binhmanobj.GeneralName + " đang bận... ");
                        return;
                    }
                    base.SetText("Biên chế quân cho theo yêu cầu cho tướng " + binhmanobj.GeneralName + "... ");

                    BienCheQuan.BienChe(binhmanobj.CityID, binhmanobj.GeneralId, binhmanobj.Military.Bobinh[0], binhmanobj.Military.KyBinh[0], binhmanobj.Military.CungThu[0], binhmanobj.Military.Xe[0]);

                    SetText("Biên chế quân giới theo yêu cầu cho tướng " + binhmanobj.GeneralName + "... ");

                    Hashtable hashtable = OPT.ChangeQuanGioi(binhmanobj.GeneralId, binhmanobj.Military.Bobinh[1], binhmanobj.Military.Bobinh[2], binhmanobj.Military.Bobinh[3],
                                    binhmanobj.Military.KyBinh[1], binhmanobj.Military.KyBinh[2], binhmanobj.Military.KyBinh[3], binhmanobj.Military.CungThu[1], binhmanobj.Military.CungThu[2], binhmanobj.Military.CungThu[3], binhmanobj.Military.Xe[1], cookies);

                    if ((hashtable == null) || (hashtable["ret"].ToString() != "0"))
                    {
                        SetText("Không biên chế được quân giới cho tướng " + binhmanobj.GeneralName + "... ");
                        return;
                    }
                    generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, binhmanobj.GeneralId);
                    if (generalMilitaryInfoEx == null) return;



                    bool flag = true;
                    if (binhmanobj.SoLuongQuanMinToGo > (((generalMilitaryInfoEx.Military.Bobinh[0] + generalMilitaryInfoEx.Military.KyBinh[0]) + generalMilitaryInfoEx.Military.CungThu[0]) + (generalMilitaryInfoEx.Military.Xe[0] * 3)))
                    {
                        SetText("Tướng " + binhmanobj.GeneralName + " không đủ quân số để đi... ");
                        flag = false;

                    }
                    if (binhmanobj.SiKhiMinToGo > generalMilitaryInfoEx.Military.SyKhi)
                    {
                        SetText("Tướng " + binhmanobj.GeneralName + " không đủ sỹ khí để đi... ");
                        flag = false;
                    }
                    if (binhmanobj.TuUpSiKhi)
                    {
                        OPT.UpSiKhi(cityID, binhmanobj.GeneralId);
                    }

                    if (flag)
                    {
                        SetText("Điều tướng " + binhmanobj.GeneralName + " đánh địa tinh tọa độ (" + binhmanobj.ToaDoMoX + ", " + binhmanobj.ToaDoMoY + "...");

                        int destX = binhmanobj.ToaDoMoX;
                        int destY = binhmanobj.ToaDoMoY;
                        int mapID = common.MapPosToMapID(destX, destY);

                        hashtable = Command.Common.TestDanhMotMucTieu(destX, destY, binhmanobj.GeneralId, 0, 0, 14);
                        if ((hashtable != null) && !(hashtable["ret"].ToString() != "0"))
                        {
                            int num12 = int.Parse(hashtable["duration"].ToString());
                            int num13 = int.Parse(((ArrayList)hashtable["dest"])[0].ToString());
                            hashtable = OPT.DanhMotMucTieu(mapID, binhmanobj.GeneralId, 0, 0, 14);
                            if ((hashtable != null) && (hashtable["ret"].ToString() == "0"))
                            {
                                base.SetText("Điều tướng " + binhmanobj.GeneralName + " đánh Địa tinh đi mất " + num12 / 60 + " phút... ");
                                return;
                            }
                        }
                        else
                        {
                            SetText(binhmanobj.GeneralName + " không đánh được địa tinh tọa độ (" + binhmanobj.ToaDoMoX + ", " + binhmanobj.ToaDoMoY + "...");

                        }
                        //return;
                    }
                    else
                    {

                        //SetText("Không điều tướng " + binhmanobj.GeneralName + " đi được do không đủ điều kiện");
                    }
                }
            }
            catch (Exception ex)
            {
                base.SetText("Không Điều tướng " + binhmanobj.GeneralName + " đánh địa tinh được, lỗi gì đó ...");
            }
        }

        private void DieuTuongDiDanhMan(ArrayList geninfo)
        {
            try
            {
                int num2;
                int num3;
                int maxOToGo = 0;
                BinhManObj obj2 = null;
                for (num2 = 0; num2 < geninfo.Count; num2++)
                {
                    obj2 = (BinhManObj)geninfo[num2];
                    if (maxOToGo < obj2.MaxOToGo)
                    {
                        maxOToGo = obj2.MaxOToGo;
                    }
                }
                base.SetText("Điều tướng " + obj2.GeneralName + "...");
                if (maxOToGo <= 6)
                {
                    num3 = 0;
                }
                else
                {
                    num3 = (maxOToGo - 6) / 11;
                    if (((maxOToGo - 6) % 11) > 0)
                    {
                        num3++;
                    }
                }
                int cityID = obj2.CityID;
                LVClient.Command.CityObj.City cityByID = LVClient.Command.City.GetCityByID(cityID);
                int x = cityByID.x;
                int y = cityByID.y;
                string cookies = LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
                LVClient.Command.City.SwitchCitySlow(cityID);
                MilitaryGeneral generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, obj2.GeneralId);
                if (generalMilitaryInfoEx != null)
                {
                    base.SetText("Điều tướng " + obj2.GeneralName + ", đang lấy th\x00f4ng tin man tr\x00ean bản đồ... ");
                    int[] manid = new int[geninfo.Count];
                    num2 = 0;
                    while (num2 < geninfo.Count)
                    {
                        manid[num2] = ((BinhManObj)geninfo[num2]).ManID;
                        num2++;
                    }
                    this.lastmapidcenter = common.MapPosToMapID(x, y);
                    this.ManMap.Clear();
                    this.FindMan(manid, this.lastmapidcenter, num3, ref this.ManMap);
                    this.lastcityX = x;
                    this.lastcityY = y;
                    if ((this.ManMap != null) && (this.ManMap.Count != 0))
                    {
                        base.SetText("Điều tướng " + obj2.GeneralName + ", t\x00ecm man mục ti\x00eau... ");
                        Npc_tentObj[] objArray = this.FindmanTarget(geninfo, this.ManMap);
                        if (objArray != null)
                        {
                            foreach (Npc_tentObj obj3 in objArray)
                            {
                                obj2 = null;
                                for (num2 = 0; num2 < geninfo.Count; num2++)
                                {
                                    if (((BinhManObj)geninfo[num2]).ManID == obj3.ManID)
                                    {
                                        obj2 = (BinhManObj)geninfo[num2];
                                        break;
                                    }
                                }
                                if (obj2 != null)
                                {
                                    int num7 = common.MapIDtoX(obj3.MapID);
                                    int num8 = common.MapIDtoY(obj3.MapID);
                                    if (common.distancefrom2poin(x, y, num7, num8) <= obj2.MaxOToGo)
                                    {
                                        Hashtable hashtable;
                                        base.SetText("Điều tướng " + obj2.GeneralName + " đánh " + Man.GetManName(obj3.ManID) + "...");
                                       
                                        
                                        base.SetText("Điều tướng " + obj2.GeneralName + ", bi\x00ean chế qu\x00e2n... ");
                                       
                                        BienCheQuan.BienChe(obj2.CityID, obj2.GeneralId, obj2.Military.Bobinh[0], obj2.Military.KyBinh[0], obj2.Military.CungThu[0], obj2.Military.Xe[0]);
                                        
                                        base.SetText("Điều tướng " + obj2.GeneralName + ", bi\x00ean chế qu\x00e2n giới... ");
                                        if (((((((obj2.Military.Bobinh[1] != 0) || (obj2.Military.Bobinh[2] != 0)) || ((obj2.Military.Bobinh[3] != 0) || (obj2.Military.KyBinh[1] != 0))) || (((obj2.Military.KyBinh[2] != 0) || (obj2.Military.KyBinh[3] != 0)) || ((obj2.Military.CungThu[1] != 0) || (obj2.Military.CungThu[2] != 0)))) || (obj2.Military.CungThu[3] != 0)) || (obj2.Military.Xe[1] != 0)) && (((((((obj2.Military.Bobinh[1] != 0) && (obj2.Military.Bobinh[1] != generalMilitaryInfoEx.Military.Bobinh[1])) || ((obj2.Military.Bobinh[2] != 0) && (obj2.Military.Bobinh[2] != generalMilitaryInfoEx.Military.Bobinh[2]))) || (((obj2.Military.Bobinh[3] != 0) && (obj2.Military.Bobinh[3] != generalMilitaryInfoEx.Military.Bobinh[3])) || ((obj2.Military.KyBinh[1] != 0) && (obj2.Military.KyBinh[1] != generalMilitaryInfoEx.Military.KyBinh[1])))) || ((((obj2.Military.KyBinh[2] != 0) && (obj2.Military.KyBinh[2] != generalMilitaryInfoEx.Military.KyBinh[2])) || ((obj2.Military.KyBinh[3] != 0) && (obj2.Military.KyBinh[3] != generalMilitaryInfoEx.Military.KyBinh[3]))) || (((obj2.Military.CungThu[1] != 0) && (obj2.Military.CungThu[1] != generalMilitaryInfoEx.Military.CungThu[1])) || ((obj2.Military.CungThu[2] != 0) && (obj2.Military.CungThu[2] != generalMilitaryInfoEx.Military.CungThu[2]))))) || ((obj2.Military.CungThu[3] != 0) && (obj2.Military.CungThu[3] != generalMilitaryInfoEx.Military.CungThu[3]))) || ((obj2.Military.Xe[1] != 0) && (obj2.Military.Xe[1] != generalMilitaryInfoEx.Military.Xe[1]))))
                                        {
                                            if (obj2.Military.Bobinh[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Bobinh[1] = obj2.Military.Bobinh[1];
                                            }
                                            if (obj2.Military.Bobinh[2] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Bobinh[2] = obj2.Military.Bobinh[2];
                                            }
                                            if (obj2.Military.Bobinh[3] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Bobinh[3] = obj2.Military.Bobinh[3];
                                            }
                                            if (obj2.Military.KyBinh[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.KyBinh[1] = obj2.Military.KyBinh[1];
                                            }
                                            if (obj2.Military.KyBinh[2] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.KyBinh[2] = obj2.Military.KyBinh[2];
                                            }
                                            if (obj2.Military.KyBinh[3] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.KyBinh[3] = obj2.Military.KyBinh[3];
                                            }
                                            if (obj2.Military.CungThu[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.CungThu[1] = obj2.Military.CungThu[1];
                                            }
                                            if (obj2.Military.CungThu[2] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.CungThu[2] = obj2.Military.CungThu[2];
                                            }
                                            if (obj2.Military.CungThu[3] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.CungThu[3] = obj2.Military.CungThu[3];
                                            }
                                            if (obj2.Military.Xe[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Xe[1] = obj2.Military.Xe[1];
                                            }
                                          
                                            hashtable = OPT.ChangeQuanGioi(obj2.GeneralId, obj2.Military.Bobinh[1], obj2.Military.Bobinh[2], obj2.Military.Bobinh[3], obj2.Military.KyBinh[1], obj2.Military.KyBinh[2], obj2.Military.KyBinh[3], obj2.Military.CungThu[1], obj2.Military.CungThu[2], obj2.Military.CungThu[3], obj2.Military.Xe[1], cookies);
                                            if ((hashtable == null) || (hashtable["ret"].ToString() != "0"))
                                            {
                                                goto Label_0C50;
                                            }
                                        }
                                        generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, obj2.GeneralId);
                                        if (generalMilitaryInfoEx == null)
                                        {
                                            return;
                                        }
                                        bool flag = true;
                                        if (obj2.SoLuongQuanMinToGo > (((generalMilitaryInfoEx.Military.Bobinh[0] + generalMilitaryInfoEx.Military.KyBinh[0]) + generalMilitaryInfoEx.Military.CungThu[0]) + (generalMilitaryInfoEx.Military.Xe[0] * 3)))
                                        {
                                            flag = false;
                                        }
                                        if (obj2.SiKhiMinToGo > generalMilitaryInfoEx.Military.SyKhi)
                                        {
                                            flag = false;
                                        }
                                        if (obj2.TuUpSiKhi)
                                        {
                                            OPT.UpSiKhi(cityID, obj2.GeneralId);
                                        }
                                        int mapID = obj3.MapID;
                                        int destX = common.MapIDtoX(mapID);
                                        int destY = common.MapIDtoY(mapID);
                                        if (flag)
                                        {
                                            hashtable = Command.Common.TestDanhMotMucTieu(destX, destY, obj2.GeneralId, 0, 0, 1);
                                            if ((hashtable != null) && !(hashtable["ret"].ToString() != "0"))
                                            {
                                                int num12 = int.Parse(hashtable["duration"].ToString());
                                                base.SetText(string.Concat(new object[] { "Điều tướng ", obj2.GeneralName, ", đánh ", Man.GetManName(obj3.ManID), " đi mất ", num12 / 60, " phút... " }));
                                                int num13 = int.Parse(((ArrayList)hashtable["dest"])[0].ToString());
                                                hashtable = OPT.DanhMotMucTieu(mapID, obj2.GeneralId, 0, 0, 1);
                                                if ((hashtable != null) && (hashtable["ret"].ToString() == "0"))
                                                {
                                                    base.SetText("Điều tướng " + obj2.GeneralName + " đánh " + Man.GetManName(obj3.ManID));
                                                }
                                            }
                                            return;
                                        }
                                    Label_0C50: ;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception)
            {
            }
        }


        /*private void DieuTuongDi(ArrayList geninfo)
        {
            try
            {
                int num2;
                int num3;
                int maxOToGo = 0;
                BinhManObj obj2 = null;
                for (num2 = 0; num2 < geninfo.Count; num2++)
                {
                    obj2 = (BinhManObj) geninfo[num2];
                    if (maxOToGo < obj2.MaxOToGo)
                    {
                        maxOToGo = obj2.MaxOToGo;
                    }
                }
                base.SetText("Điều tướng " + obj2.GeneralName + "...");
                if (maxOToGo <= 6)
                {
                    num3 = 0;
                }
                else
                {
                    num3 = (maxOToGo - 6) / 11;
                    if (((maxOToGo - 6) % 11) > 0)
                    {
                        num3++;
                    }
                }
                int cityID = obj2.CityID;
                LVClient.Command.CityObj.City cityByID = LVClient.Command.City.GetCityByID(cityID);
                int x = cityByID.x;
                int y = cityByID.y;
                string cookies = LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
                LVClient.Command.City.SwitchCitySlow(cityID);
                MilitaryGeneral generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, obj2.GeneralId);
                if (generalMilitaryInfoEx != null)
                {
                    base.SetText("Điều tướng " + obj2.GeneralName + ", đang lấy th\x00f4ng tin man tr\x00ean bản đồ... ");
                    int[] manid = new int[geninfo.Count];
                    num2 = 0;
                    while (num2 < geninfo.Count)
                    {
                        manid[num2] = ((BinhManObj) geninfo[num2]).ManID;
                        num2++;
                    }
                    this.lastmapidcenter = common.MapPosToMapID(x, y);
                    this.ManMap.Clear();
                    this.FindMan(manid, this.lastmapidcenter, num3, ref this.ManMap);
                    this.lastcityX = x;
                    this.lastcityY = y;
                    if ((this.ManMap != null) && (this.ManMap.Count != 0))
                    {
                        base.SetText("Điều tướng " + obj2.GeneralName + ", t\x00ecm man mục ti\x00eau... ");
                        Npc_tentObj[] objArray = this.FindmanTarget(geninfo, this.ManMap);
                        if (objArray != null)
                        {
                            foreach (Npc_tentObj obj3 in objArray)
                            {
                                obj2 = null;
                                for (num2 = 0; num2 < geninfo.Count; num2++)
                                {
                                    if (((BinhManObj) geninfo[num2]).ManID == obj3.ManID)
                                    {
                                        obj2 = (BinhManObj) geninfo[num2];
                                        break;
                                    }
                                }
                                if (obj2 != null)
                                {
                                    int num7 = common.MapIDtoX(obj3.MapID);
                                    int num8 = common.MapIDtoY(obj3.MapID);
                                    if (common.distancefrom2poin(x, y, num7, num8) <= obj2.MaxOToGo)
                                    {
                                        Hashtable hashtable;
                                        base.SetText("Điều tướng " + obj2.GeneralName + " đánh " + Man.GetManName(obj3.ManID) + "...");
                                        base.SetText("Điều tướng " + obj2.GeneralName + ", bi\x00ean chế qu\x00e2n... ");
                                        BienCheQuan.BienChe(obj2.CityID, obj2.GeneralId, obj2.Military.Bobinh[0], obj2.Military.KyBinh[0], obj2.Military.CungThu[0], obj2.Military.Xe[0]);
                                        base.SetText("Điều tướng " + obj2.GeneralName + ", bi\x00ean chế qu\x00e2n giới... ");
                                        if (((((((obj2.Military.Bobinh[1] != 0) || (obj2.Military.Bobinh[2] != 0)) || ((obj2.Military.Bobinh[3] != 0) || (obj2.Military.KyBinh[1] != 0))) || (((obj2.Military.KyBinh[2] != 0) || (obj2.Military.KyBinh[3] != 0)) || ((obj2.Military.CungThu[1] != 0) || (obj2.Military.CungThu[2] != 0)))) || (obj2.Military.CungThu[3] != 0)) || (obj2.Military.Xe[1] != 0)) && (((((((obj2.Military.Bobinh[1] != 0) && (obj2.Military.Bobinh[1] != generalMilitaryInfoEx.Military.Bobinh[1])) || ((obj2.Military.Bobinh[2] != 0) && (obj2.Military.Bobinh[2] != generalMilitaryInfoEx.Military.Bobinh[2]))) || (((obj2.Military.Bobinh[3] != 0) && (obj2.Military.Bobinh[3] != generalMilitaryInfoEx.Military.Bobinh[3])) || ((obj2.Military.KyBinh[1] != 0) && (obj2.Military.KyBinh[1] != generalMilitaryInfoEx.Military.KyBinh[1])))) || ((((obj2.Military.KyBinh[2] != 0) && (obj2.Military.KyBinh[2] != generalMilitaryInfoEx.Military.KyBinh[2])) || ((obj2.Military.KyBinh[3] != 0) && (obj2.Military.KyBinh[3] != generalMilitaryInfoEx.Military.KyBinh[3]))) || (((obj2.Military.CungThu[1] != 0) && (obj2.Military.CungThu[1] != generalMilitaryInfoEx.Military.CungThu[1])) || ((obj2.Military.CungThu[2] != 0) && (obj2.Military.CungThu[2] != generalMilitaryInfoEx.Military.CungThu[2]))))) || ((obj2.Military.CungThu[3] != 0) && (obj2.Military.CungThu[3] != generalMilitaryInfoEx.Military.CungThu[3]))) || ((obj2.Military.Xe[1] != 0) && (obj2.Military.Xe[1] != generalMilitaryInfoEx.Military.Xe[1]))))
                                        {
                                            if (obj2.Military.Bobinh[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Bobinh[1] = obj2.Military.Bobinh[1];
                                            }
                                            if (obj2.Military.Bobinh[2] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Bobinh[2] = obj2.Military.Bobinh[2];
                                            }
                                            if (obj2.Military.Bobinh[3] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Bobinh[3] = obj2.Military.Bobinh[3];
                                            }
                                            if (obj2.Military.KyBinh[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.KyBinh[1] = obj2.Military.KyBinh[1];
                                            }
                                            if (obj2.Military.KyBinh[2] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.KyBinh[2] = obj2.Military.KyBinh[2];
                                            }
                                            if (obj2.Military.KyBinh[3] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.KyBinh[3] = obj2.Military.KyBinh[3];
                                            }
                                            if (obj2.Military.CungThu[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.CungThu[1] = obj2.Military.CungThu[1];
                                            }
                                            if (obj2.Military.CungThu[2] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.CungThu[2] = obj2.Military.CungThu[2];
                                            }
                                            if (obj2.Military.CungThu[3] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.CungThu[3] = obj2.Military.CungThu[3];
                                            }
                                            if (obj2.Military.Xe[1] != 0)
                                            {
                                                generalMilitaryInfoEx.Military.Xe[1] = obj2.Military.Xe[1];
                                            }
                                            hashtable = OPT.ChangeQuanGioi(obj2.GeneralId, obj2.Military.Bobinh[1], obj2.Military.Bobinh[2], obj2.Military.Bobinh[3], obj2.Military.KyBinh[1], obj2.Military.KyBinh[2], obj2.Military.KyBinh[3], obj2.Military.CungThu[1], obj2.Military.CungThu[2], obj2.Military.CungThu[3], obj2.Military.Xe[1], cookies);
                                            if ((hashtable == null) || (hashtable["ret"].ToString() != "0"))
                                            {
                                                goto Label_0C50;
                                            }
                                        }
                                        generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(cityID, obj2.GeneralId);
                                        if (generalMilitaryInfoEx == null)
                                        {
                                            return;
                                        }
                                        bool flag = true;
                                        if (obj2.SoLuongQuanMinToGo > (((generalMilitaryInfoEx.Military.Bobinh[0] + generalMilitaryInfoEx.Military.KyBinh[0]) + generalMilitaryInfoEx.Military.CungThu[0]) + (generalMilitaryInfoEx.Military.Xe[0] * 3)))
                                        {
                                            flag = false;
                                        }
                                        if (obj2.SiKhiMinToGo > generalMilitaryInfoEx.Military.SyKhi)
                                        {
                                            flag = false;
                                        }
                                        if (obj2.TuUpSiKhi)
                                        {
                                            OPT.UpSiKhi(cityID, obj2.GeneralId);
                                        }
                                        int mapID = obj3.MapID;
                                        int destX = common.MapIDtoX(mapID);
                                        int destY = common.MapIDtoY(mapID);
                                        if (flag)
                                        {
											hashtable = Command.Common.TestDanhMotMucTieu(destX, destY, obj2.GeneralId, 0, 0, 1);
                                            if ((hashtable != null) && !(hashtable["ret"].ToString() != "0"))
                                            {
                                                int num12 = int.Parse(hashtable["duration"].ToString());
                                                base.SetText(string.Concat(new object[] { "Điều tướng ", obj2.GeneralName, ", đánh ", Man.GetManName(obj3.ManID), " đi mất ", num12 / 60, " phút... " }));
                                                int num13 = int.Parse(((ArrayList) hashtable["dest"])[0].ToString());
                                                hashtable = OPT.DanhMotMucTieu(mapID, obj2.GeneralId, 0, 0, 1);
                                                if ((hashtable != null) && (hashtable["ret"].ToString() == "0"))
                                                {
                                                    base.SetText("Điều tướng " + obj2.GeneralName + " đánh " + Man.GetManName(obj3.ManID));
                                                }
                                            }
                                            return;
                                        }
                                    Label_0C50:;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception)
            {
            }
        }
        */

        private void FindMan(int[] manid, long mapidcenter, ref ArrayList ret)
        {
            try
            {
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
                        for (int j = 0; j < manid.Length; j++)
                        {
                            if (manid[j] == obj2.ManID)
                            {
                                ret.Add(obj2);
                                break;
                            }
                        }
                    }
                }
            }
            catch (Exception)
            {
            }
        }

        public void FindMan(int[] manid, int mapidcenter, int rate, ref ArrayList ret)
        {
            int num = common.MapIDtoX(mapidcenter);
            int num2 = common.MapIDtoY(mapidcenter);
            for (int i = 0; i < rate; i++)
            {
                for (int j = -i; j <= i; j++)
                {
                    int num3;
                    int num4;
                    if ((j == -i) || (j == i))
                    {
                        for (int k = -i; k <= i; k++)
                        {
                            num3 = num + (j * 11);
                            num4 = num2 + (k * 11);
                            this.FindMan(manid, (long) common.MapPosToMapID(num3, num4), ref ret);
                        }
                    }
                    else
                    {
                        num3 = num + (j * 11);
                        num4 = num2 + (i * 11);
                        this.FindMan(manid, (long) common.MapPosToMapID(num3, num4), ref ret);
                        num3 = num + (j * 11);
                        num4 = num2 - (i * 11);
                        this.FindMan(manid, (long) common.MapPosToMapID(num3, num4), ref ret);
                    }
                }
                if (ret.Count > 3)
                {
                    break;
                }
            }
        }

        private Npc_tentObj[] FindmanTarget(ArrayList geninfo, ArrayList manmap)
        {
            Npc_tentObj[] objArray = null;
            if (geninfo.Count == 0)
            {
                return null;
            }
            int[] manid = new int[geninfo.Count];
            BinhManObj obj2 = null;
            for (int i = 0; i < geninfo.Count; i++)
            {
                obj2 = (BinhManObj) geninfo[i];
                manid[i] = obj2.ManID;
            }
            int uuTienID = obj2.UuTienID;
            LVClient.Command.CityObj.City cityByID = LVClient.Command.City.GetCityByID(obj2.CityID);
            int x = cityByID.x;
            int y = cityByID.y;
            int centerMapID = common.MapPosToMapID(x, y);
            switch (uuTienID)
            {
                case 1:
                    return this.FindManTargetGanNhat(centerMapID, manid, manmap);

                case 2:
                case 3:
                case 4:
                    return objArray;
            }
            return objArray;
        }

        private Npc_tentObj[] FindManTargetGanNhat(int centerMapID, int[] manid, ArrayList manmap)
        {
            Npc_tentObj obj2 = null;
            int num;
            ArrayList list = new ArrayList();
            foreach (Npc_tentObj obj3 in manmap)
            {
                num = 0;
                while (num < manid.Length)
                {
                    if (obj3.ManID == manid[num])
                    {
                        list.Add(obj3);
                    }
                    num++;
                }
            }
            Npc_tentObj[] objArray = new Npc_tentObj[list.Count];
            objArray = (Npc_tentObj[]) list.ToArray(typeof(Npc_tentObj));
            int num2 = common.MapIDtoX(centerMapID);
            int num3 = common.MapIDtoY(centerMapID);
            for (num = 0; num < objArray.Length; num++)
            {
                int num4 = common.MapIDtoX(objArray[num].MapID);
                int num6 = common.MapIDtoY(objArray[num].MapID);
                int num8 = common.distancefrom2poin(num2, num3, num4, num6);
                for (int i = num + 1; i < objArray.Length; i++)
                {
                    int num5 = common.MapIDtoX(objArray[i].MapID);
                    int num7 = common.MapIDtoY(objArray[i].MapID);
                    int num9 = common.distancefrom2poin(num2, num3, num5, num7);
                    if (num8 > num9)
                    {
                        obj2 = objArray[num];
                        objArray[num] = objArray[i];
                        objArray[i] = obj2;
                        num8 = num9;
                    }
                }
            }
            return objArray;
        }

        /*public void GetParameter(ArrayList geninfolist, int sleep)
        {
            this.Sleep = sleep;
            geninfolist.Sort();
            this.BinhManList.Clear();
            ArrayList list = null;
            int key = 0;
            for (int i = 0; i < geninfolist.Count; i++)
            {
                if (key != ((BinhManObj) geninfolist[i]).GeneralId)
                {
                    if (i != 0)
                    {
                        this.BinhManList.Add(key, list);
                    }
                    list = new ArrayList();
                    list.Add(geninfolist[i]);
                    key = ((BinhManObj) geninfolist[i]).GeneralId;
                }
                else
                {
                    list.Add(geninfolist[i]);
                }
            }
            if ((list != null) && (list.Count > 0))
            {
                this.BinhManList.Add(key, list);
            }
        }
		*/
        /*private bool isTuongDangDi(ArrayList binhmanifo)
        {
            int cityid = 0;
            int num2 = 0;
            this.lastmapidcenter = 0;
            this.lastcityX = 0;
            this.lastcityY = 0;
            try
            {
                Hashtable hashtable;
                int num3;
                int num5;
                int num7;
                BinhManObj obj2 = (BinhManObj) binhmanifo[0];
                cityid = obj2.CityID;
                string cookies = LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
                LVClient.Command.City.SwitchCitySlow(cityid);
                string parameter = "gid=16&pid=-1&tab=1&tid=0";
                Hashtable hashtable2 = Build.Execute(2, parameter, true, cookies);
                if ((hashtable2 != null) && (hashtable2["ret"].ToString() == "0"))
                {
                    ArrayList list3 = (ArrayList) hashtable2["battle"];
                    for (int i = 0; i < list3.Count; i++)
                    {
                        ArrayList list2 = (ArrayList) list3[i];
                        num5 = int.Parse(list2[0].ToString());
                        parameter = "lBattleID=" + num5;
						hashtable = Command.Common.Execute(4, parameter, true, cookies);
                        if (hashtable != null)
                        {
                            ArrayList list4 = (ArrayList) hashtable["myside"];
                            num7 = 0;
                            while (num7 < list4.Count)
                            {
                                list2 = (ArrayList) list4[0];
                                num3 = int.Parse(list2[0].ToString());
                                num2 = int.Parse(list2[13].ToString());
                                num5 = int.Parse(hashtable["battle_id"].ToString());
                                if (obj2.GeneralId == num2)
                                {
                                    //AUTOFIGHTING.startBattle(num5, 0, obj2.SoTuongMinhDanh1TuongDich, 300, obj2.PhuongThucTanCongID, obj2.PhuongThucChonMucTieuID);
									AUTOFIGHTING.startBattle(num5, 0, obj2.SoTuongMinhDanh1TuongDich, 300, obj2.PhuongThucTanCongID, obj2.PhuongThucChonMucTieuID);
                                    return true;
                                }
                                num7++;
                            }
                        }
                    }
                }
                parameter = "tid=0";
				hashtable = Command.Common.Execute(40, parameter, true, cookies);
                if (hashtable != null)
                {
                    ArrayList list5 = (ArrayList) hashtable["goto"];
                    for (num7 = 0; num7 < list5.Count; num7++)
                    {
                        ArrayList list6 = (ArrayList) list5[num7];
                        num3 = int.Parse(list6[1].ToString());
                        int sleeptime = int.Parse(list6[13].ToString());
                        num2 = int.Parse(((ArrayList) ((ArrayList) list6[8])[0])[0].ToString());
                        num5 = int.Parse(list6[4].ToString());
                        if ((obj2.GeneralId == num2) && (num3 != 0))
                        {
                            if (num3 == 2)
                            {
                                sleeptime = 0;
                            }
                            if ((num5 != 0) && ((num3 == 1) || (num3 == 2)))
                            {
                                AUTOFIGHTING.startBattle(num5, sleeptime, obj2.SoTuongMinhDanh1TuongDich, 300, obj2.PhuongThucTanCongID, obj2.PhuongThucChonMucTieuID);
                            }
                            return true;
                        }
                    }
                }
                return false;
            }
            catch (Exception)
            {
                return false;
            }
        }
		 */

		private bool isTuongDangDi1(ArrayList binhmanifo)
		{
			int cityid = 0;
			int genid = 0;
			LVClient.Command.CommonObj.BinhManObj binhmanobj;
			ArrayList geninfo;

			lastmapidcenter = 0;
			lastcityX = 0;
			lastcityY = 0;

			Hashtable result;
			ArrayList temp;

			try
			{
				binhmanobj = (LVClient.Command.CommonObj.BinhManObj)binhmanifo[0];
				cityid = binhmanobj.CityID;

				string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
				LVClient.Command.City.SwitchCitySlow(cityid);



				int status;
				int time;		//s
				int battleid;

				// check xem co đang đánh nhau khong
				string para = "gid=16&pid=-1&tab=1&tid=0";
				Hashtable result1 = LVClient.Command.Build.Execute(2, para, true, cookies);
				if (result1 != null && result1["ret"].ToString() == "0")
				{
					ArrayList battle = (ArrayList)result1["battle"];
					for (int ii = 0; ii < battle.Count; ii++)
					{
						temp = (ArrayList)battle[ii];
						battleid = int.Parse(temp[0].ToString());
						// lay thong tin chien truong
						para = "lBattleID=" + battleid;
						result = LVClient.Command.Common.Execute(4, para, true, cookies);
						if (result != null)
						{
							ArrayList myside = (ArrayList)result["myside"];
							for (int i = 0; i < myside.Count; i++)
							{
								temp = (ArrayList)myside[0];
								status = int.Parse(temp[0].ToString());
								genid = int.Parse(temp[13].ToString());
								battleid = int.Parse(result["battle_id"].ToString());
								if (binhmanobj.GeneralId == genid)
								{
									//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien );
									//LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, 0, binhmanobj.SoTuongMinhDanh1TuongDich, 300, binhmanobj.PhuongThucTanCongID, binhmanobj.PhuongThucChonMucTieuID);
									LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, 0, binhmanobj.SoTuongMinhDanh1TuongDich, arBinhManList);
									return true;
								}

							}
						}// end if (result != null)						
					} // end 					for (int i = 0; i < battle.Count; i++)

				}


				// kiem tra xem co dang di khong
				para = "tid=0";
				result = LVClient.Command.Common.Execute(40, para, true, cookies);
				//result = LVClient.Command.City.GetCityTask(cookies);
				if (result != null)
				{
					ArrayList gotobat = (ArrayList)result["goto"];
					for (int i = 0; i < gotobat.Count; i++)
					{
						ArrayList oneGotobat = (ArrayList)gotobat[i];
						status = int.Parse(oneGotobat[1].ToString());
						time = int.Parse(oneGotobat[13].ToString());		//s
						genid = int.Parse(((ArrayList)(((ArrayList)oneGotobat[8])[0]))[0].ToString());
						battleid = int.Parse(oneGotobat[4].ToString());
						if (binhmanobj.GeneralId != genid) continue;

						if (status != 0)			// Đang di hoặc đang về thao phat	 1: dang di, 2: dang danh, 3: đang trở về
						{
							if (status == 2) time = 0;
							if (battleid != 0 && (status == 1 || status == 2))
							{
								//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien );
								//LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, time, binhmanobj.SoTuongMinhDanh1TuongDich, 300, binhmanobj.PhuongThucTanCongID, binhmanobj.PhuongThucChonMucTieuID);
								LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, time, binhmanobj.SoTuongMinhDanh1TuongDich, arBinhManList);

							}
							return true;
						}
					}

				}

				return false;

			}
			catch (Exception ex)
			{
				return false;
			}


		}
  
        private void mainprocess()
        {
            try
            {
                base.Message.ForeColor = Color.Red;
                base.SetText("Đang chạy (0%)");
				int sotuongminhdanh1tuongdich =1;
                foreach (int num in this.BinhManList.Keys)
                {
                    ArrayList binhmanifo = (ArrayList) this.BinhManList[num];
					if (binhmanifo.Count ==0) continue;
					sotuongminhdanh1tuongdich = ((Command.CommonObj.BinhManObj)binhmanifo[0]).SoTuongMinhDanh1TuongDich;
                    //if ((binhmanifo.Count > 0) && !this.isTuongDangDi(binhmanifo))

                    base.SetText("Kiểm tra tướng " +  ((Command.CommonObj.BinhManObj)binhmanifo[0]).GeneralName + " ... ");

                    if (binhmanifo.Count > 0 && !LVClient.Command.CityObj.General.isTuongDangBusy(binhmanifo, sotuongminhdanh1tuongdich))
                    {
                        if (((Command.CommonObj.BinhManObj)binhmanifo[0]).ManType == 1)
                            this.DieuTuongDiDanhMan(binhmanifo);
                        else
                            this.DieuTuongDiDanhDiaTinh(binhmanifo);
                    }
                    else
                    {
                        base.SetText("Tướng " + ((Command.CommonObj.BinhManObj)binhmanifo[0]).GeneralName + " đang bận. ");
                    }
                }
            }
            catch (Exception ex)
            {
            }
        }

        public override void run()
        {
            base.IsRun = true;
            while (true)
            {
                if ((this.BinhManList == null) || (this.BinhManList.Count == 0))
                {
                    base.SetText("Chẳng c\x00f3 g\x00ec để chạy cả");
                    return;
                }
                base.SetText("Chờ tới phi\x00ean (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
                base.threadID = "BINHMAN_" + DateTime.Now.Ticks;
                ThreadManager.TakeResourceAndRun(base.threadID, new ThreadStart(this.mainprocess));
                base.Message.ForeColor = Color.Blue;
                base.SetText(string.Concat(new object[] { "Đang ngủ ", this.Sleep / 0xea60, " phút, chờ t\x00ed (mới chạy lúc: ", DateTime.Now.ToString("HH:mm:ss"), ")" }));
                if (base.MainProcessResult > 0xf4240)
                {
                    base.SetText(string.Concat(new object[] { "Bị kh\x00f3a đến ", DateTime.Now.AddSeconds((double) (base.MainProcessResult - 0xf4240)).ToString("HH:mm:ss"), ". Đang ngủ ", this.Sleep / 0xea60, " phút, chờ t\x00ed (mới chạy lúc: ", DateTime.Now.ToString("HH:mm:ss"), ")" }));
                }
                Thread.Sleep(this.Sleep);
            }
        }
    }
}

