using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Text;
using System.Windows.Forms;

namespace LVClient
{
	public partial class frmLoading : Form
	{
		string text = "Loading.......";
		public frmLoading()
		{
			InitializeComponent();
			//lblText.Text = text;
		}

		public frmLoading(string t)
		{
			InitializeComponent();
			text = t;
		}

		private void frmLoading_Load(object sender, EventArgs e)
		{
			lblText.Text = text;
			
		}
	}
}