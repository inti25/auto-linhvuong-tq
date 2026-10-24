using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using LVClient.Command.CommonObj;
using System.Drawing;
using LVClient.Common;


namespace LVClient.LVThread
{
	public class AUTOCALLMAN : ThreadSkeleton
	{

		private Hashtable CallManList = new Hashtable();		//BinhManList[GeneralId,  BinhManObj]
		private ArrayList arCallManList = new ArrayList();		// chứa  BinhManObj không bị trùng, phục vụ cho  AUTOFIGHTING
        private ArrayList gencallmanlist = new ArrayList();     // chứa thông tin list truyền vào

		public AUTOCALLMAN(System.Windows.Forms.Label lbl)
        {
            base.Message = lbl;
        }


        /// <summary>
        /// Set parameter 
        /// </summary>
        /// <param name="geninfolist">List of CallManObj </param>
        /// <param name="sleep">Time to run repeat (ms)</param>
		public void GetParameter(ArrayList geninfolist, int sleep)
		{
			this.Sleep = sleep;

            gencallmanlist = geninfolist;
			geninfolist.Sort();

            this.CallManList.Clear();
			arCallManList.Clear();
			ArrayList list = null;
			CallManObj callManObj = null;
			int key = -100;
			for (int i = 0; i < geninfolist.Count; i++)
			{
				callManObj = (CallManObj)geninfolist[i];
				if (key != callManObj.GroupID)
				{
					if (i != 0)
					{
						this.CallManList.Add(key, list);
						arCallManList.Add(callManObj);
					}
					list = new ArrayList();
					list.Add(geninfolist[i]);
					key = callManObj.GroupID;
				}
				else
				{
					list.Add(geninfolist[i]);
				}
			}
			if ((list != null) && (list.Count > 0))
			{
				this.CallManList.Add(key, list);
				arCallManList.Add(callManObj);
			}
		}


		public override void run()
		{
			base.IsRun = true;
			while (true)
			{
				if ((this.CallManList == null) || (this.CallManList.Count == 0))
				{
					base.SetText("Chẳng có gì để chạy cả");
					return;
				}
				base.SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				base.threadID = "CALLMAN_" + DateTime.Now.Ticks;
				LVClient.Common.ThreadManager.TakeResourceAndRun(base.threadID, new System.Threading.ThreadStart(this.mainprocess));
				base.Message.ForeColor = System.Drawing.Color.Blue;
				base.SetText(string.Concat(new object[] { "Đang ngủ ", this.Sleep / 0xea60, " phút, chờ t\x00ed (mới chạy lúc: ", DateTime.Now.ToString("HH:mm:ss"), ")" }));
				if (base.MainProcessResult > 0xf4240)
				{
					base.SetText(string.Concat(new object[] { "Bị kh\x00f3a đến ", DateTime.Now.AddSeconds((double)(base.MainProcessResult - 0xf4240)).ToString("HH:mm:ss"), ". Đang ngủ ", this.Sleep / 0xea60, " phút, chờ t\x00ed (mới chạy lúc: ", DateTime.Now.ToString("HH:mm:ss"), ")" }));
				}
				System.Threading.Thread.Sleep(this.Sleep);
			}
		}


		private void mainprocess()
		{
			try
			{
                const int countmaxscreen = 300;
                const int maxO = 655;
				const int minO = -655;

                int x,y, mapid;
                int sotuongminhdanh1tuongdich = 1;

                ArrayList gencallmanlisttmp = new ArrayList();
                Command.CommonObj.CallManObj callmanobj;

                LVClient.Command.CityObj.MilitaryGeneral generalMilitaryInfoEx;


                base.Message.ForeColor = Color.Red;
                base.SetText("Đang chạy (0%)");
				
				

                for (int i = 0; i < gencallmanlist.Count; i++)
                {
                    // kiem tra tình trạng các tướng
                    callmanobj = (Command.CommonObj.CallManObj)gencallmanlist[i];
                    sotuongminhdanh1tuongdich = callmanobj.SoTuongMinhDanh1TuongDich;
                    SetText("Kiểm tra tình trạng tướng " + callmanobj.GeneralName + "...");
                    // đang bận đi thì thôi
                    if (LVClient.Command.CityObj.General.isTuongDangBusy(callmanobj, sotuongminhdanh1tuongdich))
                    {
                        SetText("Tướng " + callmanobj.GeneralName + " đang bận...");
                        continue;
                    }
                    // có bnaj làm gì khác không
                    generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(callmanobj.CityID, callmanobj.GeneralId);
                    if (generalMilitaryInfoEx == null)
                    {
                        SetText("Tướng " + callmanobj.GeneralName + " đang bận hoặc lỗi không lấy được thông tin...");
                        continue;
                    }
                    gencallmanlisttmp.Add(gencallmanlist[i]);
                }
                              

                int screencount = 0;

                Npc_tentObj[] manFound;
                Npc_tentObj mantemp;
                
                bool canrun;
                Random rand = new Random();

                while (screencount < countmaxscreen)
                {
                    if (gencallmanlisttmp.Count == 0) return;

                    //Toaj do tim man
                    x = rand.Next(minO, maxO);
                    y = rand.Next(minO, maxO);
                    mapid = Common.common.MapPosToMapID(x, y);

                    SetText("Tìm man " + screencount + "/" + countmaxscreen + " screens ...");
                    manFound = LVClient.Command.Map.FindMan(mapid);

                    if (manFound == null || manFound.Length == 0)
                    {
                        screencount++;
                        continue;
                    }

                    bool found = false;

                    for (int i = 0; i < manFound.Length; i++)
                    {
                        for (int j = 0; j < gencallmanlisttmp.Count; j++)
                        {
                            callmanobj = (Command.CommonObj.CallManObj)gencallmanlisttmp[j];
                            found = false;
                            canrun = true;
                            for (int k = 0; k < callmanobj.Mans.Count; k++)
                            {
                                if (manFound[i].ManID == ((Command.CommonObj.ManOBJ)callmanobj.Mans[k]).ManID)
                                {
                                    found = true;
                                    break;
                                }
                            }

                            if (!found) continue;
                            SetText("Tìm thấy " + Man.GetManName(manFound[i].ManID) + " ..." );


                            // chuaanr bi tuong
                            canrun = ChuanBiTuong(callmanobj);
                            if (!canrun)
                            {
                                gencallmanlisttmp.Remove(callmanobj);
                                j = j - 1;
                                continue;
                            }

                            mantemp = KiemTraODat(callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY);

                            // dieu man ve
                            if (mantemp == null)
                            {
                                mantemp = DieuManVe(manFound[i], callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY);

                            }



                            if (mantemp == null)
                            {   
                                // kiem tra o dat lan nua
                                mantemp = KiemTraODat(callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY);
                                if (mantemp == null)
                                {
                                    canrun = false;
                                    gencallmanlisttmp.RemoveAt(i);
                                    break;
                                }
                            }

                            // dieu di
                            if (canrun)
                            {
                                // kiểm tra lại lần nữa
                                for (int m = 0; m < callmanobj.Mans.Count; m++)
                                {
                                    if (mantemp.ManID == ((Command.CommonObj.ManOBJ)callmanobj.Mans[m]).ManID)
                                    {
                                        found = true;
                                        break;
                                    }
                                }

                                if (found)
                                {
                                    if (CuTuongDi(callmanobj, mantemp))
                                    {
                                        gencallmanlisttmp.Remove(callmanobj);
                                        j = j - 1;
                                        screencount = 0;
                                        canrun = false;
                                    }
                                    else
                                    {

                                        SetText("Oopp! lỗi khỉ gì đó rồi, đợi chạy vòng sau...");
                                    }
                                }
                                break;
                            }
                            //  } // if (manFound[i].ManID == (Command.CommonObj.ManOBJ) callmanobj.Mans[k])
                            //} //  for (int k = 0; k < callmanobj.Mans.Count; k++)

                            // if (!canrun) break;

                        }   //  for (int j = 0; j < gencallmanlisttmp.Count; j++)
                    } //  for (int i = 0; i < manFound.Length; i++)
                }
			}
			catch (Exception ex)
			{
			}
		}


        /// <summary>
        /// Chuẩn bị tướng để đi, bao gồm biên chế quân, luyện sỹ khí, kiểm tra số lượng quân và sỹ khí
        /// </summary>
        /// <param name="gen"></param>
        /// <returns>true: ok, false: tèo</returns>
        private bool ChuanBiTuong(Command.CommonObj.CallManObj gen)
        {
            try
            {
                bool ret = true;

                SetText("Biên chế quân cho " + gen.GeneralName + "...");
                if (gen.TuBienCheQuan && gen.CityID > 0)
                {
                    LVClient.Common.BienCheQuan.BienChe(gen.CityID, gen.GeneralId,
                            gen.Military.Bobinh[0], gen.Military.KyBinh[0],
                            gen.Military.CungThu[0], gen.Military.Xe[0]);
                }



                LVClient.Command.CityObj.MilitaryGeneral generalMilitaryInfoEx  = Command.Common.GetGeneralMilitaryInfoINCityNTrai(gen.CityID, gen.GeneralId);


                if (generalMilitaryInfoEx == null)
                {
                    ret = false;
                    return ret;
                }
                //kiểm tra số lượng quân
                if (generalMilitaryInfoEx.Military.Bobinh[0] + generalMilitaryInfoEx.Military.KyBinh[0]
                    + generalMilitaryInfoEx.Military.CungThu[0] + generalMilitaryInfoEx.Military.Xe[0] * 3
                    < gen.SoLuongQuanMinToGo) ret = false;

                if (generalMilitaryInfoEx.Military.SyKhi < gen.SiKhiMinToGo) ret = false;

                //Luyện sỹ khí
                if (gen.TuUpSiKhi && gen.Military.SyKhi < 100)
                {
                    SetText("Up sỹ khí" + gen.GeneralName + "....");
                    //GeneralThaoPhat.Military.SyKhi = gArray.Military.SyKhi;
                    Command.OPT.UpSiKhi(gen.CityID, gen.GeneralId);
                }

                return ret;

            }
            catch (Exception ex)
            {
                return false;
            }

        }


        /// <summary>
        /// Kiểm tra xem tại 1 vị tri ô đất có man ko
        /// </summary>
        /// <param name="x">toạ độ x cần kiểm tra</param>
        /// <param name="y">toạ độ y cần kiểm tra</param>
        /// <returns>null nếu không có man, nếu có thì trả về Npc_tentObj</returns>
        private Npc_tentObj KiemTraODat(int x, int y)
        {

            try
            {
                int mapid = Common.common.MapPosToMapID(x, y);

                Npc_tentObj[] manFound = LVClient.Command.Map.FindMan(mapid);
                if (manFound == null || manFound.Length == 0) return null;
                LVClient.Command.CommonObj.Npc_tentObj npcten;
                bool datok = true;
                int manid = 0;
                for (int i = 0; i < manFound.Length; i++)
                {
                    npcten = (LVClient.Command.CommonObj.Npc_tentObj)manFound[i];
                    if (npcten.MapID == mapid)
                    {
                        return npcten;
                    }
                }

                return null;

            }
            catch (Exception ex)
            {
                return null;
            }
        }


        /// <summary>
        /// Điều man về
        /// </summary>
        /// <param name="mancandieu">Npc_tentObj</param>
        /// <param name="xChuyenDen"></param>
        /// <param name="yChuyenDen"></param>
        /// <returns>null nếu không điều được,Npc_tentObj nếu điều được </returns>
        private Npc_tentObj DieuManVe(Npc_tentObj mancandieu, int xChuyenDen, int yChuyenDen)
        {

            try
            {
                int MapIDChuyenDen = Common.common.MapPosToMapID(xChuyenDen, yChuyenDen);
                Npc_tentObj npcten = null;

                string para = "type=63";
                para += "&param1=" + mancandieu.BatleId;
                para += "&param2=" + MapIDChuyenDen;
                para += "&paytype=0";

                Hashtable ret = Command.OPT.Execute(69, para, true);

                if (ret == null) return null;

                int retid = int.Parse(ret["ret"].ToString());

                switch (retid)
                {

                    case 0:				// ok
                        SetText("Đã gọi thành công " + Man.GetManName(npcten.ManID) + " về tọa độ (" + xChuyenDen + ", " + yChuyenDen + ")...");
                        npcten = new Npc_tentObj();
                        npcten.MapID = MapIDChuyenDen;

                        return npcten;
                    //break;

                    // không có man tộc lệnh
                    case 90:
                        SetText("Không gọi được " + Man.GetManName(npcten.ManID) + " vì hết man tộc lệnh...");


                        break;

                    case 39:
                        SetText("Ô đất (" + xChuyenDen + ", " + yChuyenDen + ") đã bị chiếm ...");

                        return null;

                    case 209:
                        SetText("Man đã mất ...");
                        break;

                    default:
                        SetText("Gọi man bị lỗi " + retid + "...");
                        break;
                }

                return null;
            }
            catch (Exception ex)
            {
                return null;
            }
        }


        private bool CuTuongDi(Command.CommonObj.CallManObj callmanobj, Npc_tentObj npcten)
        {

            try
            {
                bool goOK = false;
                int time = 0;

                // try để lấy time
                Hashtable hashtable =
                    Command.Common.TestDanhMotMucTieu(callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY, callmanobj.GeneralId, 0, 0, 1);


                if ((hashtable != null) && !(hashtable["ret"].ToString() != "0"))
                {
                    time = int.Parse(hashtable["duration"].ToString());
                }

                int MapID = Common.common.MapPosToMapID(callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY);
                hashtable = LVClient.Command.OPT.DanhMotMucTieu(MapID, callmanobj.GeneralId, 0, 0, 1);
                if ((hashtable != null) && (hashtable["ret"].ToString() == "0"))
                {
                    goOK = true;
                    LVClient.LVThread.AUTOFIGHTING.startBattle(npcten.BatleId, time,
                        callmanobj.SoTuongMinhDanh1TuongDich, callmanobj);



                    base.SetText("Điều tướng " + callmanobj.GeneralName + " đánh " + Man.GetManName(npcten.ManID) + " mất " + time / 60 + " phút.");
                }
                

                // đang bận đi thì thôi
                LVClient.Command.CityObj.General.isTuongDangBusy(callmanobj, callmanobj.SoTuongMinhDanh1TuongDich) ;

                  
                    //int num13 = int.Parse(((ArrayList)hashtable["dest"])[0].ToString());

                   
                
                return goOK;
            }
            catch (Exception ex)
            {
                return false;
            }

        }

        /*private void mainprocess()
        {
            try
            {
              


                base.Message.ForeColor = Color.Red;
                base.SetText("Đang chạy (0%)");
                int sotuongminhdanh1tuongdich = 1;




                foreach (int num in this.CallManList.Keys)
                {
                    ArrayList callmanifo = (ArrayList)this.CallManList[num];
                    if (callmanifo.Count == 0) continue;

                    sotuongminhdanh1tuongdich = ((Command.CommonObj.CallManObj)callmanifo[0]).SoTuongMinhDanh1TuongDich;

                    if ((callmanifo.Count > 0) && !LVClient.Command.CityObj.General.isTuongDangBusy(callmanifo, sotuongminhdanh1tuongdich))
                    {
                        this.DieuTuongDi(callmanifo);
                    }
                }
            }
            catch (Exception)
            {
            }
        }
        */
		/// <summary>
		/// 
		/// </summary>
		/// <param name="callmanifo"></param>
		private void DieuTuongDi(ArrayList callmanifo)
		{
			try
			{
				LVClient.Command.CommonObj.CallManObj callmanobj;
				LVClient.Command.CityObj.MilitaryGeneral generalMilitaryInfoEx;
				bool genisok = true;

				int callX = 0;
				int callY = 0;
				LVClient.Command.CommonObj.Npc_tentObj npcten = null;
				int MapID;
				// duyeetj tung tuong
				for (int genidx = 0; genidx < callmanifo.Count; genidx++)
				{
					bool canrun = true;
					npcten = null;

					callmanobj = (LVClient.Command.CommonObj.CallManObj)callmanifo[genidx];
					callX = callmanobj.ToaDoCallVeX;
					callY = callmanobj.ToaDoCallVeY;

					// kiểm tra tình trạng tướng
					if (callmanobj.CityID > 0)		// thành
						generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(callmanobj.CityID, callmanobj.GeneralId);
					else  // trại
						generalMilitaryInfoEx = Command.Common.GetGeneralInforInLuyenBinh(callmanobj.CityID, callmanobj.GeneralId);

					if (generalMilitaryInfoEx == null)
					{
						genisok = false;
						continue;
					}

					
					if (generalMilitaryInfoEx.Military.SyKhi < callmanobj.SiKhiMinToGo) canrun = false;

					if (canrun)
					{
						// Kiểm tra tình trạng ô đất
						SetText("Kiểm tra ô đất (" + callX + ", " + callY + ")...");
						MapID = Common.common.MapPosToMapID(callX, callY);
						ArrayList man = null;
						Command.Map.FindMan(MapID, ref man);
					
						bool datok = true;
						int manid = 0;
						for (int i = 0; i < man.Count; i++)
						{
							npcten = (LVClient.Command.CommonObj.Npc_tentObj)man[i];
							if (npcten.MapID == MapID)
							{
								datok = false;
								manid = npcten.ManID;
								SetText("Ô đất (" + callX + ", " + callY + ") đang có man " + Man.GetManName(manid));
								break;
							}
						}

						if (datok) npcten = null;

						//Kiểm tra tình trạng man tộc???

						// gọi về
						man.Clear();
						if (genisok && datok)
						{
							for (int i = 0; i < callmanifo.Count; i++)
							{
								//callmanobj = (LVClient.Command.CommonObj.CallManObj)callmanifo[i];

								man.AddRange(((LVClient.Command.CommonObj.CallManObj)callmanifo[i]).Mans);
							}

							if (man.Count > 0)
							{
								SetText("Tìm man và gọi về ...");
								npcten = FindNCallMan(man, callX, callY);
							}
						}
					}
					
					//Biên chế quân
					if (genisok && npcten != null && callmanobj.TuBienCheQuan)
					{
						SetText("Biên chế quân cho " + callmanobj.GeneralName + "...");
						LVClient.Common.BienCheQuan.BienChe(callmanobj.CityID, callmanobj.GeneralId,
								callmanobj.Military.Bobinh[0], callmanobj.Military.KyBinh[0],
								callmanobj.Military.CungThu[0], callmanobj.Military.Xe[0]);

					}

			

					// kiểm tra tình trạng tướng
					if (callmanobj.CityID > 0)		// thành
						generalMilitaryInfoEx = Command.Common.GetGeneralMilitaryInfoEx(callmanobj.CityID, callmanobj.GeneralId);
					else  // trại
						generalMilitaryInfoEx = Command.Common.GetGeneralInforInLuyenBinh(callmanobj.CityID, callmanobj.GeneralId);
					
					if (generalMilitaryInfoEx == null) continue;

					//kiểm tra số lượng quân
					if (generalMilitaryInfoEx.Military.Bobinh[0] + generalMilitaryInfoEx.Military.KyBinh[0]
						+ generalMilitaryInfoEx.Military.CungThu[0] + generalMilitaryInfoEx.Military.Xe[0] * 3
						< callmanobj.SoLuongQuanMinToGo) canrun = false;

					if (generalMilitaryInfoEx.Military.SyKhi < callmanobj.SiKhiMinToGo) canrun = false;
					
					//Luyện sỹ khí
					if (callmanobj.TuUpSiKhi && callmanobj.Military.SyKhi < 100)
					{
						SetText("Up sỹ khí" + callmanobj.GeneralName + "....");
						//GeneralThaoPhat.Military.SyKhi = gArray.Military.SyKhi;
						Command.OPT.UpSiKhi(callmanobj.CityID, callmanobj.GeneralId);
					}				
						
					//Cử đi
					if (canrun)
					{
						Hashtable hashtable =
							Command.Common.TestDanhMotMucTieu(callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY, callmanobj.GeneralId, 0, 0, 1);
						if ((hashtable != null) && !(hashtable["ret"].ToString() != "0"))
						{
							int time = int.Parse(hashtable["duration"].ToString());
							base.SetText(string.Concat(new object[] { "Điều tướng ", callmanobj.GeneralName, ", đánh ", 
								Man.GetManName(npcten.ManID), " đi mất ", time / 60, " phút... " }));
							int num13 = int.Parse(((ArrayList)hashtable["dest"])[0].ToString());

							MapID = Common.common.MapPosToMapID(callmanobj.ToaDoCallVeX, callmanobj.ToaDoCallVeY);
							hashtable = LVClient.Command.OPT.DanhMotMucTieu(MapID, callmanobj.GeneralId, 0, 0, 1);
							if ((hashtable != null) && (hashtable["ret"].ToString() == "0"))
							{
								LVClient.LVThread.AUTOFIGHTING.startBattle(npcten.BatleId, time,
									callmanobj.SoTuongMinhDanh1TuongDich, callmanifo);
								base.SetText("Điều tướng " + callmanobj.GeneralName + " đánh " + Man.GetManName(npcten.ManID));
							}
						}
						//return;
					}


				} // for (int genidx = 0; genidx < callmanifo.Count; genidx++)
			}
			catch (Exception ex)
			{
			}
		}

		/// <summary>
		/// Tìm và call man về
		/// </summary>
		/// <param name="manid">Danh sách LVClient.Command.CommonObj.ManOBJ cần tìm để call</param>
		/// <param name="x"> Tọa độ X sẽ call về</param>
		/// <param name="y">Tọa độ Y sẽ call về</param>
		/// <returns>LVClient.Command.CommonObj.Npc_tentObj</returns>
		private LVClient.Command.CommonObj.Npc_tentObj FindNCallMan(ArrayList ManOBJ, int xCallVe, int yCallVe)
		{
			try
			{
				const int maxO = 655;
				const int minO = -655;

				const int NumOfRepeat = 300;
				LVClient.Command.CommonObj.Npc_tentObj npcreturn = null;

				int MapIDChuyenDen = Common.common.MapPosToMapID(xCallVe, yCallVe);


				int count = 0;

				int x, y, mapid;
				Random rand = new Random();
				ArrayList man = new ArrayList();
				LVClient.Command.CommonObj.Npc_tentObj npcten = null;
				LVClient.Command.CommonObj.ManOBJ sourceMan;


				while (count < NumOfRepeat)
				{
					count++;

					if (ManOBJ.Count == 0) break;

					SetText("Tìm man .... " + count + "/" + NumOfRepeat + " screen." );

					x = rand.Next(minO, maxO);
					y = rand.Next(minO, maxO);
					mapid = Common.common.MapPosToMapID(x, y);
					man.Clear(); 
					Command.Map.FindMan(mapid, ref man);
					if (man.Count == 0) continue;

					bool foundman = false;
					for (int i = 0; i < man.Count; i++)
					{
						npcten = (LVClient.Command.CommonObj.Npc_tentObj)man[i];
						for (int j = 0; j < ManOBJ.Count; j++)
						{
							sourceMan = (LVClient.Command.CommonObj.ManOBJ)ManOBJ[j];
							if (npcten.ManID == sourceMan.ManID)
							{
								foundman = true;
								SetText("Đã tìm thấy man " + Man.GetManName(npcten.ManID) + "....");
								break;
							}
						}
						if (foundman) break;
					}

					// khoong thaays
					if (!foundman) continue;

					// call npcten ve
					if (foundman)
					{
						string para = "type=63";
						para += "&param1=" + npcten.BatleId;
						para += "&param2=" + MapIDChuyenDen;
						para += "&paytype=0";

						Hashtable ret = Command.OPT.Execute(69, para, true);


						if (ret != null)
						{
							int retid = int.Parse(ret["ret"].ToString());

							switch (retid)
							{

								case 0:				// ok
									SetText("Đã gọi thành công " + Man.GetManName(npcten.ManID) + " về tọa độ (" + xCallVe + ", " + yCallVe + ")...");
									npcten.MapID = MapIDChuyenDen;
									npcreturn = npcten;
									return npcreturn;
								//break;

								// không có man tộc lệnh
								case 90:
									SetText("Không gọi được " + Man.GetManName(npcten.ManID) + " vì hết man tộc lệnh...");

									for (int i = 0; i < ManOBJ.Count; i++)
									{
										sourceMan = (LVClient.Command.CommonObj.ManOBJ)ManOBJ[i];
										if (npcten.ManID == sourceMan.ManID)
										{

											//ManOBJ.RemoveAt(i);
										}

									}
									break;

								case 39:
									SetText("Ô đất (" + xCallVe + ", " + yCallVe + ") đã bị chiếm ...");

									return null;

								default:
									SetText("Gọi man bị lỗi " + retid + "...");
									break;

							}

						}

					}
					else
					{

						SetText("Tìm man .... Đen quá, chẳng tìm thấy thằng nào, để lượt khác vậy.");

					}

				}

				return npcreturn;
			}
			catch (Exception ex)
			{
				return null;
			}

		}


    




	}
}
