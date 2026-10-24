using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;

namespace LVClient.Command.OPTObj {
    public partial class wepon : UserControl {
        public int cityid=0;
        public int posid_w = 0;
        public int posid_h = 0;
        public int posid_a = 0;
        public wepon() 
		{
            InitializeComponent();
        }

		private void cboWepon_SelectedIndexChanged(object sender, EventArgs e)
		{

		}
    }
}