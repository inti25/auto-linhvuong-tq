using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;
using System.Net.Sockets;
using System.Windows.Forms;

namespace LVClient.Web {
    public class LoginInfo {
        public string SessionId;
        public string sg_tag;
        public string login_name;
        public string cid;
        public string tid;
        public string timeout;
        public string uid;
        public string today;
        public string sg_cur_uid_1;
        public string uname;
        public string head_img;
        public string ally_id;
        public LoginInfo(string cookies) {
            string[] temp = cookies.Split(new char[] { '~' }, 2);
            LVClient.Web.LVWeb.Server = int.Parse(temp[0]);
            string[] temp1 = temp[1].Split(new char[] { ';' });
            foreach (string item in temp1) {
                if (item != null) {
                    string[] arritem = item.Split(new char[] { '=' }, 2);
                    if (arritem.Length > 1) {
                        string[] arritemdata = arritem[1].Split(new char[] { ';' });
                        switch (arritem[0].Trim()) {
                            case "ASP.NET_SessionId":
                                SessionId = arritemdata[0];
                                break;
                            case "sg_tag":
                                sg_tag = arritemdata[0];
                                break;
                            case "login_name":
                                login_name = arritemdata[0];
                                break;
                            case "cid":
                                cid = arritemdata[0];
                                break;
                            case "tid":
                                tid = arritemdata[0];
                                break;
                            case "timeout":
                                timeout = arritemdata[0];
                                break;
                            case "uid":
                                uid = arritemdata[0];
                                break;
                            case "today":
                                today = arritemdata[0];
                                break;
                            case "sg_cur_uid_1":
                                sg_cur_uid_1 = arritemdata[0];
                                break;
                            case "uname":
                                uname = arritemdata[0];
                                break;
                            case "head_img":
                                head_img = arritemdata[0];
                                break;
                            case "ally_id":
                                ally_id = arritemdata[0];
                                break;
                        }
                    }
                }
            }
        }
        public LoginInfo(string[] cookies) {
            foreach (string item in cookies) {
                if (item != null) {
                    string[] arritem = item.Split(new char[] { '=' }, 2);
                    if (arritem.Length > 1) {
                        string[] arritemdata = arritem[1].Split(new char[] { ';' });
                        switch (arritem[0].Trim()) {
                            case "ASP.NET_SessionId":
                                SessionId = arritemdata[0];
                                break;
                            case "sg_tag":
                                sg_tag = arritemdata[0];
                                break;
                            case "login_name":
                                login_name = arritemdata[0];
                                break;
                            case "cid":
                                cid = arritemdata[0];
                                break;
                            case "tid":
                                tid = arritemdata[0];
                                break;
                            case "timeout":
                                timeout = arritemdata[0];
                                break;
                            case "uid":
                                uid = arritemdata[0];
                                break;
                            case "today":
                                today = arritemdata[0];
                                break;
                            case "sg_cur_uid_1":
                                sg_cur_uid_1 = arritemdata[0];
                                break;
                            case "uname":
                                uname = arritemdata[0];
                                break;
                            case "head_img":
                                head_img = arritemdata[0];
                                break;
                            case "ally_id":
                                ally_id = arritemdata[0];
                                break;
                        }
                    }
                }
            }
        }
        public string MakeCookiesString() {
			
            return "sg_cur_uid_1=" + sg_cur_uid_1 + "; __utma=177481006.3759498242394892300.1231373307.1231373307.1231373307.1; __utmz=177481006.1231373307.1.1.utmcsr=s" + LVWeb.Server + ".linhvuong.zooz.vn|utmccn=(referral)|utmcmd=referral|utmcct=/news/66/134/index.htm; __utma=70309261.407652934.1231393052.1232513857.1232518914.54; __utmz=70309261.1231821835.20.2.utmcsr=diendan.vtc.vn|utmccn=(referral)|utmcmd=referral|utmcct=/tan_cong_thanh_qua_6_lan/m_4477486/tm.htm; __utmc=70309261; __utmb=70309261.1.10.1232518914; ASP.NET_SessionId=" + SessionId + "; sg_tag=" + sg_tag + "; login_name=" + login_name + "; cid=" + cid + "; tid=" + tid + "; timeout=" + timeout + "; uid=" + uid + "; today=" + today + "; uname=" + uname + "; head_img=" + head_img + "; ally_id=" + ally_id + "; infoall=1; mid=184561; _float_left=350px; _float_top=124px; nid=; link=city";
        }
        public string MakeCookiesString(int cityid) {
            return "sg_cur_uid_1=" + sg_cur_uid_1 + "; __utma=177481006.3759498242394892300.1231373307.1231373307.1231373307.1; __utmz=177481006.1231373307.1.1.utmcsr=linhvuong.zooz.vn|utmccn=(referral)|utmcmd=referral|utmcct=/news/66/134/index.htm; __utma=70309261.407652934.1231393052.1232513857.1232518914.54; __utmz=70309261.1231821835.20.2.utmcsr=diendan.vtc.vn|utmccn=(referral)|utmcmd=referral|utmcct=/tan_cong_thanh_qua_6_lan/m_4477486/tm.htm; __utmc=70309261; __utmb=70309261.1.10.1232518914; ASP.NET_SessionId=" + SessionId + "; sg_tag=" + sg_tag + "; login_name=" + login_name + "; cid=" + cityid + "; tid=" + tid + "; timeout=" + timeout + "; uid=" + uid + "; today=" + today + "; uname=" + uname + "; head_img=" + head_img + "; ally_id=" + ally_id + "; infoall=1; mid=184561; _float_left=350px; _float_top=124px; nid=; link=city";
        }
    }
}
